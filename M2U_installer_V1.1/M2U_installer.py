import maya.cmds as cmds
import maya.mel as mel
import json
import os
import re
import math
import datetime

WINDOW_NAME = "mayaUnrealV233SingleFileWindow"
EXPORT_FOLDER_FIELD = "mayaUnrealV233ExportFolderField"
POLYCOUNT_FIELD = "mayaUnrealV233PolycountField"
RESULT_SCROLL_FIELD = "mayaUnrealV233ResultScrollField"

DEFAULT_POLYCOUNT_LIMIT = 50000
PIVOT_DISTANCE_LIMIT = 0.001
VALIDATION_REPORT_FILENAME = "maya_unreal_v2_3_3_validation_report.json"
EXPORT_REPORT_FILENAME = "maya_unreal_v2_3_3_export_report.json"

CUSTOM_SHELF_NAME = "M2U_Tools"
SHELF_BUTTON_LABEL = "M2U Export"
SHELF_BUTTON_ANNOTATION = "Validate and export Unreal-ready FBX assets"
ICON_FILENAME = "M2U_icon.png"

GENERIC_NAME_PATTERNS = [
    r"^pCube\d+$",
    r"^pSphere\d+$",
    r"^pCylinder\d+$",
    r"^pPlane\d+$",
    r"^pTorus\d+$",
    r"^polySurface\d+$",
    r"^group\d+$",
    r"^transform\d+$",
]

BLOCKING_CHECK_NAMES = set([
    "Mesh Presence Check",
    "Name Check",
    "Freeze Transform Check",
    "Polycount Check",
])

UNIT_TO_CM = {
    "mm": 0.1,
    "millimeter": 0.1,
    "cm": 1.0,
    "centimeter": 1.0,
    "m": 100.0,
    "meter": 100.0,
    "km": 100000.0,
    "kilometer": 100000.0,
    "in": 2.54,
    "inch": 2.54,
    "ft": 30.48,
    "foot": 30.48,
    "yd": 91.44,
    "yard": 91.44,
}


def is_generic_name(node_name):
    short_name = node_name.split("|")[-1]
    for pattern in GENERIC_NAME_PATTERNS:
        if re.match(pattern, short_name):
            return True
    return False


def sanitize_asset_name(name):
    short_name = name.split("|")[-1]
    safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", short_name)
    safe = safe.strip("_")
    if not safe:
        safe = "unnamed_asset"
    return safe


def display_name_from_path(path_value):
    if not path_value:
        return "None"
    normalized = path_value.replace("\\", "/")
    return normalized.split("/")[-1]


def strip_full_path(path_value):
    if not path_value:
        return None
    return display_name_from_path(path_value)


def get_selected_transforms():
    return cmds.ls(selection=True, long=True, type="transform") or []


def get_mesh_shapes(transform):
    shapes = cmds.listRelatives(transform, shapes=True, fullPath=True) or []
    return [shape for shape in shapes if cmds.nodeType(shape) == "mesh"]


def has_mesh(transform):
    return len(get_mesh_shapes(transform)) > 0


def get_polycount(transform):
    total_faces = 0
    for shape in get_mesh_shapes(transform):
        faces = cmds.polyEvaluate(shape, face=True) or 0
        total_faces += int(faces)
    return total_faces


def get_transform_values(transform):
    t = cmds.xform(transform, query=True, translation=True, objectSpace=True)
    r = cmds.xform(transform, query=True, rotation=True, objectSpace=True)
    s = cmds.xform(transform, query=True, scale=True, relative=True)
    return {
        "translate": (float(t[0]), float(t[1]), float(t[2])),
        "rotate": (float(r[0]), float(r[1]), float(r[2])),
        "scale": (float(s[0]), float(s[1]), float(s[2])),
    }


def get_rotate_pivot(transform):
    pivot = cmds.xform(transform, query=True, rotatePivot=True, worldSpace=True)
    return (float(pivot[0]), float(pivot[1]), float(pivot[2]))


def get_scene_linear_unit():
    return cmds.currentUnit(query=True, linear=True)


def get_unit_scale_to_cm(unit_name):
    return UNIT_TO_CM.get(unit_name, None)


def get_bounding_box_dimensions_cm(transform):
    if not has_mesh(transform):
        return {
            "width_cm": None,
            "height_cm": None,
            "depth_cm": None,
            "raw_width": None,
            "raw_height": None,
            "raw_depth": None,
            "unit": get_scene_linear_unit(),
            "skipped": True,
        }

    unit_name = get_scene_linear_unit()
    unit_scale = get_unit_scale_to_cm(unit_name)
    bbox = cmds.exactWorldBoundingBox(transform)
    width = abs(float(bbox[3]) - float(bbox[0]))
    height = abs(float(bbox[4]) - float(bbox[1]))
    depth = abs(float(bbox[5]) - float(bbox[2]))

    if unit_scale is None:
        return {
            "width_cm": None,
            "height_cm": None,
            "depth_cm": None,
            "raw_width": width,
            "raw_height": height,
            "raw_depth": depth,
            "unit": unit_name,
            "skipped": False,
        }

    return {
        "width_cm": width * unit_scale,
        "height_cm": height * unit_scale,
        "depth_cm": depth * unit_scale,
        "raw_width": width,
        "raw_height": height,
        "raw_depth": depth,
        "unit": unit_name,
        "skipped": False,
    }


def has_history(transform):
    history = cmds.listHistory(transform) or []
    ignored_types = set(["transform", "groupId", "shadingEngine", "objectSet", "mesh"])
    meaningful = [node for node in history if cmds.nodeType(node) not in ignored_types]
    return len(meaningful) > 0


def approx_zero(values, tolerance=0.0001):
    return all(abs(v) <= tolerance for v in values)


def approx_one(values, tolerance=0.0001):
    return all(abs(v - 1.0) <= tolerance for v in values)


def distance_from_origin(values):
    x, y, z = values
    return math.sqrt((x * x) + (y * y) + (z * z))


def make_check(name, passed, message, severity):
    return {
        "name": name,
        "passed": passed,
        "message": message,
        "severity": severity,
        "blocking": name in BLOCKING_CHECK_NAMES,
    }


def check_scene_unit():
    unit_name = get_scene_linear_unit()
    if unit_name not in ["cm", "centimeter"]:
        return make_check(
            "Scene Unit Check",
            False,
            "Scene linear unit is '%s'. Unreal pipeline is usually safest when Maya uses centimeters." % unit_name,
            "warning",
        )
    return make_check(
        "Scene Unit Check",
        True,
        "Scene linear unit is set to centimeters.",
        "info",
    )


def check_name(transform):
    if is_generic_name(transform):
        return make_check(
            "Name Check",
            False,
            "Generic/default object name found. Rename to a meaningful asset name.",
            "error",
        )
    return make_check(
        "Name Check",
        True,
        "Object name looks meaningful.",
        "info",
    )


def check_has_mesh(transform):
    mesh_shapes = get_mesh_shapes(transform)
    if not mesh_shapes:
        return make_check(
            "Mesh Presence Check",
            False,
            "Selected transform has no mesh shape under it.",
            "error",
        )
    return make_check(
        "Mesh Presence Check",
        True,
        "Found %d mesh shape(s)." % len(mesh_shapes),
        "info",
    )


def check_frozen_transforms(transform):
    values = get_transform_values(transform)
    is_frozen = (
        approx_zero(values["translate"]) and
        approx_zero(values["rotate"]) and
        approx_one(values["scale"])
    )
    if not is_frozen:
        return make_check(
            "Freeze Transform Check",
            False,
            "Transforms are not frozen. T=%s R=%s S=%s" % (
                values["translate"],
                values["rotate"],
                values["scale"],
            ),
            "error",
        )
    return make_check(
        "Freeze Transform Check",
        True,
        "Transforms look frozen.",
        "info",
    )


def check_pivot(transform):
    pivot = get_rotate_pivot(transform)
    distance = distance_from_origin(pivot)
    if distance > PIVOT_DISTANCE_LIMIT:
        return make_check(
            "Pivot Check",
            False,
            "Pivot is not near world origin. Pivot=%s, distance=%.6f" % (pivot, distance),
            "warning",
        )
    return make_check(
        "Pivot Check",
        True,
        "Pivot is near origin.",
        "info",
    )


def check_polycount(transform, limit):
    polycount = get_polycount(transform)
    if polycount > limit:
        return make_check(
            "Polycount Check",
            False,
            "Polycount is high: %d faces (limit: %d)." % (polycount, limit),
            "error",
        )
    return make_check(
        "Polycount Check",
        True,
        "Polycount is within limit: %d/%d faces." % (polycount, limit),
        "info",
    )


def check_history(transform):
    if has_history(transform):
        return make_check(
            "History Check",
            False,
            "Construction history detected. Delete history before export.",
            "warning",
        )
    return make_check(
        "History Check",
        True,
        "No meaningful construction history detected.",
        "info",
    )


def check_asset_scale_sanity(transform):
    if not has_mesh(transform):
        return make_check(
            "Asset Scale Check",
            True,
            "Scale check skipped because the selected transform has no mesh shape.",
            "info",
        )

    dims = get_bounding_box_dimensions_cm(transform)
    if dims["width_cm"] is None:
        return make_check(
            "Asset Scale Check",
            False,
            "Could not convert scene units to centimeters. Scale sanity check skipped.",
            "warning",
        )

    width_cm = dims["width_cm"]
    height_cm = dims["height_cm"]
    depth_cm = dims["depth_cm"]
    longest = max(width_cm, height_cm, depth_cm)
    shortest = min(width_cm, height_cm, depth_cm)

    if longest < 1.0:
        return make_check(
            "Asset Scale Check",
            False,
            "Asset dimensions look extremely small for Unreal. Longest side is %.2f cm." % longest,
            "warning",
        )

    if longest > 1000.0:
        return make_check(
            "Asset Scale Check",
            False,
            "Asset dimensions look extremely large for Unreal. Longest side is %.2f cm." % longest,
            "warning",
        )

    if shortest == 0.0:
        return make_check(
            "Asset Scale Check",
            False,
            "One bounding-box dimension is zero. Review mesh scale and thickness.",
            "warning",
        )

    return make_check(
        "Asset Scale Check",
        True,
        "Asset dimensions look Unreal-compatible. Size in cm: %.2f x %.2f x %.2f" % (
            width_cm, height_cm, depth_cm
        ),
        "info",
    )


def get_check_recommendation(check, transform, polycount_limit):
    name = check["name"]

    if check["passed"]:
        passed_map = {
            "Name Check": "Naming looks valid.",
            "Freeze Transform Check": "Transforms are clean.",
            "Pivot Check": "Pivot placement looks acceptable.",
            "Polycount Check": "Polycount is within the current limit.",
            "History Check": "History is clean.",
            "Mesh Presence Check": "Mesh data exists.",
            "Scene Unit Check": "Scene units are readable for the pipeline.",
            "Asset Scale Check": "No scale action is needed right now.",
        }
        return passed_map.get(name, "No action needed.")

    if name == "Mesh Presence Check":
        return "Select a transform that contains a mesh shape before validating or exporting."
    if name == "Name Check":
        short_name = transform.split("|")[-1]
        suggested_name = "SM_" + short_name.replace("pCube1", "Asset_A")
        return "Rename the asset to a meaningful production-style name, for example: %s" % suggested_name
    if name == "Freeze Transform Check":
        return "Use Modify > Freeze Transformations before export."
    if name == "Pivot Check":
        return "Review pivot placement. Keep it where gameplay, placement, or modular snapping needs it."
    if name == "Polycount Check":
        return "Reduce the face count or raise the validation limit if this asset is intentionally high detail. Current limit: %d" % polycount_limit
    if name == "History Check":
        return "Delete construction history before export."
    if name == "Scene Unit Check":
        return "Consider switching Maya linear working units to centimeters for a more predictable Unreal pipeline."
    if name == "Asset Scale Check":
        return "Review the bounding box size in centimeters and compare it with the expected real-world size in Unreal."
    return "Review this issue before export."


def calculate_score(checks):
    score = 100
    for check in checks:
        if check["passed"]:
            continue
        if check["severity"] == "error":
            score -= 20
        elif check["severity"] == "warning":
            score -= 8
    return max(score, 0)


def is_ready_for_export(checks):
    for check in checks:
        if (not check["passed"]) and check.get("blocking", False):
            return False
    return True


def get_blocking_failures(checks):
    return [check["name"] for check in checks if (not check["passed"]) and check.get("blocking", False)]


def get_failed_checks(checks):
    return [check["name"] for check in checks if not check["passed"]]


def count_by_severity(checks):
    error_count = 0
    warning_count = 0
    passed_count = 0

    for check in checks:
        if check["severity"] == "error" and not check["passed"]:
            error_count += 1
        elif check["severity"] == "warning" and not check["passed"]:
            warning_count += 1
        elif check["passed"]:
            passed_count += 1

    return {
        "error_count": error_count,
        "warning_count": warning_count,
        "passed_count": passed_count,
        "issue_count": error_count + warning_count,
    }


def get_asset_status(checks, ready_for_export):
    severity_counts = count_by_severity(checks)
    if not ready_for_export:
        return "blocked"
    if severity_counts["warning_count"] > 0:
        return "warning"
    return "clean"


def build_asset_summary(transform, checks, ready_for_export):
    short_name = transform.split("|")[-1]
    blocking_failures = get_blocking_failures(checks)
    warnings = [check["name"] for check in checks if (not check["passed"]) and check["severity"] == "warning"]

    if ready_for_export and not warnings:
        return "%s is ready for export with no issues." % short_name
    if ready_for_export and warnings:
        return "%s is export-ready, but review these warnings: %s." % (short_name, ", ".join(warnings))
    return "%s is not ready for export. Fix these blocking issues first: %s." % (short_name, ", ".join(blocking_failures))


def build_asset_report(transform, polycount_limit):
    checks = [
        check_scene_unit(),
        check_has_mesh(transform),
        check_name(transform),
        check_frozen_transforms(transform),
        check_pivot(transform),
        check_polycount(transform, polycount_limit),
        check_history(transform),
        check_asset_scale_sanity(transform),
    ]

    for check in checks:
        check["recommendation"] = get_check_recommendation(check, transform, polycount_limit)

    ready = is_ready_for_export(checks)
    severity_counts = count_by_severity(checks)
    dims = get_bounding_box_dimensions_cm(transform)

    return {
        "transform": transform,
        "asset_name": transform.split("|")[-1],
        "asset_status": get_asset_status(checks, ready),
        "scene_linear_unit": get_scene_linear_unit(),
        "bounding_box_cm": {
            "width_cm": dims["width_cm"],
            "height_cm": dims["height_cm"],
            "depth_cm": dims["depth_cm"],
            "skipped": dims["skipped"],
        },
        "mesh_shapes": get_mesh_shapes(transform),
        "polycount": get_polycount(transform),
        "checks": checks,
        "score": calculate_score(checks),
        "ready_for_export": ready,
        "blocking_failures": get_blocking_failures(checks),
        "failed_checks": get_failed_checks(checks),
        "issue_count": severity_counts["issue_count"],
        "warning_count": severity_counts["warning_count"],
        "error_count": severity_counts["error_count"],
        "passed_count": severity_counts["passed_count"],
        "summary": build_asset_summary(transform, checks, ready),
    }


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def ensure_directory(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def load_fbx_plugin():
    if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
        try:
            cmds.loadPlugin("fbxmaya")
        except Exception as exc:
            raise RuntimeError("Could not load fbxmaya plugin: %s" % exc)


def set_fbx_export_defaults():
    cmds.FBXResetExport()
    cmds.FBXExportSmoothingGroups("-v", True)
    cmds.FBXExportTangents("-v", True)
    cmds.FBXExportSmoothMesh("-v", True)
    cmds.FBXExportInstances("-v", False)
    cmds.FBXExportReferencedAssetsContent("-v", False)
    cmds.FBXExportBakeComplexAnimation("-v", False)
    cmds.FBXExportAnimationOnly("-v", False)
    cmds.FBXExportSkins("-v", True)
    cmds.FBXExportShapes("-v", True)
    cmds.FBXExportInAscii("-v", False)
    cmds.FBXExportInputConnections("-v", False)
    cmds.FBXExportEmbeddedTextures("-v", False)
    cmds.FBXExportCameras("-v", False)
    cmds.FBXExportLights("-v", False)


def export_selected_to_fbx(transform, export_path):
    load_fbx_plugin()
    set_fbx_export_defaults()
    cmds.select(clear=True)
    cmds.select(transform, replace=True)
    normalized = export_path.replace("\\", "/")
    cmds.FBXExport("-f", normalized, "-s")


def build_export_report(validation_report, export_folder, fbx_path, export_success, message):
    asset = validation_report["assets"][0]
    return {
        "tool": "Maya -> Unreal V2.3.3 Single File Helper",
        "timestamp": datetime.datetime.now().isoformat(),
        "asset_name": asset["asset_name"],
        "source_transform": asset["transform"],
        "ready_for_export": asset["ready_for_export"],
        "asset_status": asset["asset_status"],
        "blocking_failures": asset["blocking_failures"],
        "failed_checks": asset["failed_checks"],
        "warning_count": asset["warning_count"],
        "error_count": asset["error_count"],
        "export_success": export_success,
        "export_folder": strip_full_path(export_folder),
        "fbx_filename": strip_full_path(fbx_path),
        "message": message,
        "validation_report_filename": VALIDATION_REPORT_FILENAME,
        "export_report_filename": EXPORT_REPORT_FILENAME,
        "full_local_paths_removed": True,
    }


def validate_selected(polycount_limit=DEFAULT_POLYCOUNT_LIMIT):
    selected = get_selected_transforms()

    if len(selected) == 0:
        cmds.warning("No transform selected. Please select one object and run again.")
        return {}

    if len(selected) > 1:
        cmds.warning("Please select only one object for V2.3.3 export helper.")
        return {}

    asset_report = build_asset_report(selected[0], polycount_limit)

    return {
        "tool": "Maya -> Unreal V2.3.3 Validation",
        "asset_count": 1,
        "polycount_limit": polycount_limit,
        "blocking_checks": sorted(list(BLOCKING_CHECK_NAMES)),
        "assets": [asset_report],
    }


def export_selected_valid_asset(export_folder, polycount_limit=DEFAULT_POLYCOUNT_LIMIT):
    if not export_folder:
        cmds.warning("Please provide an export folder path.")
        return {}

    validation_report = validate_selected(polycount_limit=polycount_limit)
    if not validation_report:
        return {}

    asset = validation_report["assets"][0]
    asset_name = sanitize_asset_name(asset["asset_name"])

    ensure_directory(export_folder)

    validation_report_path = os.path.join(export_folder, VALIDATION_REPORT_FILENAME)
    save_json(validation_report, validation_report_path)

    fbx_path = os.path.join(export_folder, asset_name + ".fbx")
    export_report_path = os.path.join(export_folder, EXPORT_REPORT_FILENAME)

    if not asset["ready_for_export"]:
        message = "Export cancelled because the asset failed blocking validation checks."
        export_report = build_export_report(
            validation_report=validation_report,
            export_folder=export_folder,
            fbx_path=None,
            export_success=False,
            message=message,
        )
        save_json(export_report, export_report_path)
        return {
            "validation_report": validation_report,
            "export_report": export_report,
            "validation_report_path": validation_report_path,
            "export_report_path": export_report_path,
        }

    try:
        export_selected_to_fbx(asset["transform"], fbx_path)
        message = "FBX export completed successfully."
        export_success = True
    except Exception as exc:
        message = "FBX export failed: %s" % exc
        export_success = False
        fbx_path = None

    export_report = build_export_report(
        validation_report=validation_report,
        export_folder=export_folder,
        fbx_path=fbx_path,
        export_success=export_success,
        message=message,
    )

    save_json(export_report, export_report_path)

    return {
        "validation_report": validation_report,
        "export_report": export_report,
        "validation_report_path": validation_report_path,
        "export_report_path": export_report_path,
    }


def format_validation_for_ui(validation_report):
    if not validation_report:
        return "No validation result."

    asset = validation_report["assets"][0]
    lines = []
    lines.append("Maya -> Unreal V2.3.3 Validation")
    lines.append("=" * 50)
    lines.append("Asset: %s" % asset["asset_name"])
    lines.append("Status: %s" % asset["asset_status"])
    lines.append("Ready for Export: %s" % asset["ready_for_export"])
    lines.append("Polycount: %s" % asset["polycount"])
    lines.append("Scene Unit: %s" % asset["scene_linear_unit"])
    lines.append("Blocking Failures: %s" % asset["blocking_failures"])
    lines.append("Summary: %s" % asset["summary"])
    lines.append("")
    lines.append("Checks:")
    for check in asset["checks"]:
        state = "PASS" if check["passed"] else "FAIL"
        blocking_text = "blocking" if check["blocking"] else "non-blocking"
        lines.append("- [%s] %s (%s, %s)" % (state, check["name"], check["severity"], blocking_text))
        lines.append("  Message: %s" % check["message"])
        lines.append("  Recommendation: %s" % check["recommendation"])
    return "\n".join(lines)


def format_export_for_ui(result):
    if not result:
        return "No export result."

    export_report = result["export_report"]
    validation_report = result["validation_report"]
    asset = validation_report["assets"][0]

    lines = []
    lines.append("Maya -> Unreal V2.3.3 Export")
    lines.append("=" * 50)
    lines.append("Asset: %s" % asset["asset_name"])
    lines.append("Status: %s" % asset["asset_status"])
    lines.append("Ready for Export: %s" % asset["ready_for_export"])
    lines.append("Export Success: %s" % export_report["export_success"])
    lines.append("Message: %s" % export_report["message"])
    lines.append("Export Folder: %s" % display_name_from_path(export_report["export_folder"]))
    lines.append("FBX File: %s" % export_report.get("fbx_filename", "None"))
    lines.append("Validation Report: %s" % display_name_from_path(result.get("validation_report_path")))
    lines.append("Export Report: %s" % display_name_from_path(result.get("export_report_path")))
    lines.append("Blocking Failures: %s" % export_report["blocking_failures"])
    return "\n".join(lines)


def set_result_text(message):
    if cmds.scrollField(RESULT_SCROLL_FIELD, exists=True):
        cmds.scrollField(RESULT_SCROLL_FIELD, edit=True, text=message)


def browse_export_folder(*args):
    result = cmds.fileDialog2(fileMode=3, caption="Choose Export Folder")
    if result and len(result) > 0:
        cmds.textFieldButtonGrp(EXPORT_FOLDER_FIELD, edit=True, text=result[0])


def get_ui_values():
    export_folder = cmds.textFieldButtonGrp(EXPORT_FOLDER_FIELD, query=True, text=True)
    polycount_limit = cmds.intFieldGrp(POLYCOUNT_FIELD, query=True, value1=True)
    return export_folder, polycount_limit


def validate_from_ui(*args):
    export_folder, polycount_limit = get_ui_values()
    _ = export_folder
    report = validate_selected(polycount_limit=polycount_limit)
    set_result_text(format_validation_for_ui(report))


def export_from_ui(*args):
    export_folder, polycount_limit = get_ui_values()
    result = export_selected_valid_asset(export_folder=export_folder, polycount_limit=polycount_limit)
    set_result_text(format_export_for_ui(result))


def launch_ui():
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    cmds.window(WINDOW_NAME, title="M2U Export Helper", widthHeight=(700, 560), sizeable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8)
    cmds.text(label="Validate and export one selected asset to FBX", align="left", height=24)

    cmds.textFieldButtonGrp(
        EXPORT_FOLDER_FIELD,
        label="Export Folder",
        text="",
        buttonLabel="Browse",
        buttonCommand=browse_export_folder,
        adjustableColumn=2,
        columnAlign=(1, "left"),
    )

    cmds.intFieldGrp(
        POLYCOUNT_FIELD,
        label="Polycount Limit",
        value1=DEFAULT_POLYCOUNT_LIMIT,
        adjustableColumn=2,
        columnAlign=(1, "left"),
    )

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(340, 340))
    cmds.button(label="Validate Selected", height=36, command=validate_from_ui)
    cmds.button(label="Export Selected", height=36, command=export_from_ui)
    cmds.setParent("..")

    cmds.separator(height=8, style="in")
    cmds.scrollField(RESULT_SCROLL_FIELD, editable=False, wordWrap=True, text="Select one asset, choose an export folder, then validate or export.", height=420)
    cmds.showWindow(WINDOW_NAME)


def _get_shelf_top_level():
    return mel.eval('$tmpVar=$gShelfTopLevel')


def _ensure_custom_shelf():
    shelf_top = _get_shelf_top_level()
    shelves = cmds.tabLayout(shelf_top, query=True, childArray=True) or []

    if CUSTOM_SHELF_NAME not in shelves:
        cmds.shelfLayout(CUSTOM_SHELF_NAME, parent=shelf_top)
    cmds.tabLayout(shelf_top, edit=True, selectTab=CUSTOM_SHELF_NAME)
    return CUSTOM_SHELF_NAME


def _build_shelf_command(script_path):
    normalized = os.path.abspath(script_path).replace("\\", "/")
    return 'exec(open(r"{0}", encoding="utf-8").read(), globals())\nlaunch_ui()'.format(normalized)


def _find_icon_path(script_path):
    if not script_path:
        return None
    folder = os.path.dirname(os.path.abspath(script_path))
    candidate = os.path.join(folder, ICON_FILENAME)
    if os.path.exists(candidate):
        return candidate.replace("\\", "/")
    return None


def install_shelf_button_with_path(script_path):
    if not script_path or not os.path.exists(script_path):
        cmds.warning("Installer file not found: %s" % script_path)
        return

    target_shelf = _ensure_custom_shelf()
    command = _build_shelf_command(script_path)
    icon_path = _find_icon_path(script_path)

    existing = cmds.shelfLayout(target_shelf, query=True, childArray=True) or []
    for child in existing:
        try:
            label = cmds.shelfButton(child, query=True, label=True)
            if label == SHELF_BUTTON_LABEL:
                cmds.deleteUI(child)
        except Exception:
            pass

    kwargs = {
        "parent": target_shelf,
        "label": SHELF_BUTTON_LABEL,
        "annotation": SHELF_BUTTON_ANNOTATION,
        "command": command,
        "sourceType": "Python",
    }

    if icon_path:
        kwargs["image1"] = icon_path
        kwargs["style"] = "iconOnly"
    else:
        kwargs["imageOverlayLabel"] = "M2U"
        kwargs["style"] = "textOnly"

    cmds.shelfButton(**kwargs)

    print("Shelf button created on shelf: %s" % target_shelf)
    if icon_path:
        print("Shelf button created with icon support.")
    else:
        print("Icon not found. Falling back to text button.")


def install_and_launch_from_path(script_path):
    if script_path and os.path.exists(script_path):
        install_shelf_button_with_path(script_path)
    launch_ui()


def install_and_launch():
    try:
        script_path = os.path.abspath(__file__)
    except Exception:
        script_path = None

    install_and_launch_from_path(script_path)
