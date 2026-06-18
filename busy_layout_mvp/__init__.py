bl_info = {
    "name": "Busy Layout MVP",
    "author": "ChatGPT for 너무바쁜베짱이",
    "version": (0, 8, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Busy Layout",
    "description": "SketchUp LayOut-style MVP for Blender: orthographic cameras, real scale presets, section-cut plan render, simple dimensions, sheets, and HTML/PDF-ready output.",
    "category": "3D View",
}

import bpy
import html
import struct
import zlib
from pathlib import Path
from collections import deque
from mathutils import Vector
from datetime import date


VIEW_SPECS = [
    {"key": "TOP_PLAN", "name": "BL_TOP_PLAN", "label": "평면도 / Top Plan", "direction": Vector((0, 0, -1)), "prop": "view_top", "zoom_prop": "zoom_top"},
    {"key": "FRONT_ELEVATION", "name": "BL_FRONT_ELEVATION", "label": "정면도 / Front Elevation", "direction": Vector((0, -1, 0)), "prop": "view_front", "zoom_prop": "zoom_front"},
    {"key": "RIGHT_ELEVATION", "name": "BL_RIGHT_ELEVATION", "label": "우측면도 / Right Elevation", "direction": Vector((-1, 0, 0)), "prop": "view_right", "zoom_prop": "zoom_right"},
    {"key": "LEFT_ELEVATION", "name": "BL_LEFT_ELEVATION", "label": "좌측면도 / Left Elevation", "direction": Vector((1, 0, 0)), "prop": "view_left", "zoom_prop": "zoom_left"},
    {"key": "BACK_ELEVATION", "name": "BL_BACK_ELEVATION", "label": "배면도 / Back Elevation", "direction": Vector((0, 1, 0)), "prop": "view_back", "zoom_prop": "zoom_back"},
    {"key": "ISO_VIEW", "name": "BL_ISO_VIEW", "label": "아이소 뷰 / Iso View", "direction": Vector((-1, -1, -0.8)), "prop": "view_iso", "zoom_prop": "zoom_iso"},
]

PAPER_PRESETS = {
    "A4": {"landscape": (297, 210), "portrait": (210, 297)},
    "A3": {"landscape": (420, 297), "portrait": (297, 420)},
    "A2": {"landscape": (594, 420), "portrait": (420, 594)},
}


def drawing_objects(context, selected_only=False):
    if selected_only:
        objs = [o for o in context.selected_objects if o.visible_get()]
    else:
        objs = [o for o in context.scene.objects if o.visible_get()]

    valid_types = {"MESH", "CURVE", "SURFACE", "FONT", "META"}
    result = []
    for obj in objs:
        if obj.type not in valid_types:
            continue
        if not hasattr(obj, "bound_box"):
            continue
        if obj.name.startswith("BL_"):
            continue
        result.append(obj)
    return result


def mesh_objects_for_boolean(objs):
    return [o for o in objs if o.type == "MESH" and hasattr(o, "modifiers")]


def world_bbox_corners(objs):
    corners = []
    for obj in objs:
        try:
            for c in obj.bound_box:
                corners.append(obj.matrix_world @ Vector(c))
        except Exception:
            continue
    return corners


def bbox_min_max(corners):
    if not corners:
        return Vector((-5, -5, -5)), Vector((5, 5, 5))
    xs = [p.x for p in corners]
    ys = [p.y for p in corners]
    zs = [p.z for p in corners]
    return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))


def bbox_center_and_diag(corners):
    min_v, max_v = bbox_min_max(corners)
    center = (min_v + max_v) * 0.5
    diag = max((max_v - min_v).length, 1.0)
    return center, diag


def get_or_create_collection(name):
    coll = bpy.data.collections.get(name)
    if coll:
        return coll
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll


def get_or_create_camera(name):
    obj = bpy.data.objects.get(name)
    if obj and obj.type == "CAMERA":
        return obj

    cam_data = bpy.data.cameras.new(name + "_DATA")
    cam_obj = bpy.data.objects.new(name, cam_data)
    coll = get_or_create_collection("Busy Layout Cameras")
    coll.objects.link(cam_obj)
    return cam_obj


def look_at(obj, target):
    direction = target - obj.location
    if direction.length == 0:
        direction = Vector((0, 0, -1))
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def fit_orthographic_camera(camera, corners, margin=1.12, res_x=2480, res_y=1754):
    bpy.context.view_layer.update()
    inv = camera.matrix_world.inverted()
    local = [inv @ p for p in corners]
    xs = [p.x for p in local]
    ys = [p.y for p in local]
    width = max(xs) - min(xs) if xs else 10.0
    height = max(ys) - min(ys) if ys else 10.0
    aspect = max(res_x, 1) / max(res_y, 1)
    ortho_scale = max(height, width / aspect) * margin
    camera.data.ortho_scale = max(ortho_scale, 0.001)


def png_force_border_background_white(path, tolerance=10):
    path = Path(path)
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return False

    pos = 8
    width = height = color_type = None
    chunks = []
    idat = b""
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        chunk_type = data[pos + 4:pos + 8]
        chunk_data = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", chunk_data)
            if bit_depth != 8 or compression != 0 or filter_method != 0 or interlace != 0 or color_type not in {2, 6}:
                return False
        elif chunk_type == b"IDAT":
            idat += chunk_data
            continue
        chunks.append((chunk_type, chunk_data))

    channels = 4 if color_type == 6 else 3
    stride = width * channels
    raw = zlib.decompress(idat)
    rows = []
    index = 0
    previous = bytearray(stride)

    for _ in range(height):
        filter_type = raw[index]
        index += 1
        scan = bytearray(raw[index:index + stride])
        index += stride
        recon = bytearray(stride)
        for i, value in enumerate(scan):
            left = recon[i - channels] if i >= channels else 0
            up = previous[i]
            upper_left = previous[i - channels] if i >= channels else 0
            if filter_type == 0:
                recon[i] = value
            elif filter_type == 1:
                recon[i] = (value + left) & 255
            elif filter_type == 2:
                recon[i] = (value + up) & 255
            elif filter_type == 3:
                recon[i] = (value + ((left + up) // 2)) & 255
            elif filter_type == 4:
                predictor = left + up - upper_left
                pa = abs(predictor - left)
                pb = abs(predictor - up)
                pc = abs(predictor - upper_left)
                predict = left if pa <= pb and pa <= pc else up if pb <= pc else upper_left
                recon[i] = (value + predict) & 255
            else:
                return False
        rows.append(recon)
        previous = recon

    def rgb_at(x, y):
        offset = x * channels
        return tuple(rows[y][offset:offset + 3])

    samples = [
        rgb_at(0, 0),
        rgb_at(width - 1, 0),
        rgb_at(0, height - 1),
        rgb_at(width - 1, height - 1),
    ]
    background = tuple(sorted(channel_values)[len(channel_values) // 2] for channel_values in zip(*samples))

    def is_background(x, y):
        pixel = rgb_at(x, y)
        return all(abs(pixel[i] - background[i]) <= tolerance for i in range(3))

    visited = set()
    queue = deque()
    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.popleft()
        if x < 0 or y < 0 or x >= width or y >= height or (x, y) in visited:
            continue
        if not is_background(x, y):
            continue
        visited.add((x, y))
        offset = x * channels
        rows[y][offset:offset + 3] = b"\xff\xff\xff"
        if channels == 4:
            rows[y][offset + 3] = 255
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    if not visited:
        return False

    filtered = bytearray()
    for row in rows:
        filtered.append(0)
        filtered.extend(row)

    new_chunks = []
    wrote_idat = False
    for chunk_type, chunk_data in chunks:
        if chunk_type == b"IDAT":
            continue
        if chunk_type == b"IEND" and not wrote_idat:
            new_chunks.append((b"IDAT", zlib.compress(bytes(filtered), 9)))
            wrote_idat = True
        new_chunks.append((chunk_type, chunk_data))

    out = bytearray(data[:8])
    for chunk_type, chunk_data in new_chunks:
        out.extend(struct.pack(">I", len(chunk_data)))
        out.extend(chunk_type)
        out.extend(chunk_data)
        out.extend(struct.pack(">I", zlib.crc32(chunk_type + chunk_data) & 0xffffffff))
    path.write_bytes(out)
    return True


def scale_denominator(props):
    if props.scale_preset == "CUSTOM":
        return max(float(props.custom_scale_denominator), 0.001)
    try:
        return float(props.scale_preset)
    except Exception:
        return 50.0


def scale_display_label(props):
    if props.scale_mode == "AUTO_FIT":
        return "Auto Fit"
    denominator = scale_denominator(props)
    if abs(denominator - round(denominator)) < 0.0001:
        denominator_text = str(int(round(denominator)))
    else:
        denominator_text = f"{denominator:g}"
    label = f"1:{denominator_text}"
    if (
        props.real_scale_margin_factor and abs(props.real_scale_margin_factor - 1.0) > 0.0001
    ) or getattr(props, "real_scale_safe_margin_mm", 0.0) > 0.0001:
        label += " adjusted"
    return label


def view_scale_display_label(props, view_key):
    if props.scale_mode == "REAL_SCALE" and view_key == "ISO_VIEW" and props.real_scale_iso_auto_fit:
        return "Auto Fit"
    return scale_display_label(props)


def model_unit_display(props):
    return "meter" if props.model_unit == "METER" else "millimeter"


def real_scale_ortho_scale(props, res_x=2480, res_y=1754):
    denominator = scale_denominator(props)
    safe_margin_mm = max(float(getattr(props, "real_scale_safe_margin_mm", 0.0)), 0.0)
    viewport_width_mm = props.viewport_width_mm + safe_margin_mm * 2.0
    viewport_height_mm = props.viewport_height_mm + safe_margin_mm * 2.0
    if props.model_unit == "MILLIMETER":
        viewport_height_world = viewport_height_mm * denominator
        viewport_width_world = viewport_width_mm * denominator
    else:
        viewport_height_world = viewport_height_mm * denominator / 1000.0
        viewport_width_world = viewport_width_mm * denominator / 1000.0

    camera_aspect = max(float(res_x), 1.0) / max(float(res_y), 1.0)
    required_height = viewport_height_world
    required_width_as_height = viewport_width_world / camera_aspect
    ortho_scale = max(required_height, required_width_as_height) * max(props.real_scale_margin_factor, 0.001)
    return max(ortho_scale, 0.001)


def set_camera_ortho_scale(camera, corners, props):
    view_key = camera.get("busy_layout_view", "")
    if props.scale_mode == "REAL_SCALE" and not (view_key == "ISO_VIEW" and props.real_scale_iso_auto_fit):
        camera.data.ortho_scale = real_scale_ortho_scale(props, props.resolution_x, props.resolution_y)
        return

    zoom_prop = ""
    for spec in VIEW_SPECS:
        if spec["key"] == view_key:
            zoom_prop = spec.get("zoom_prop", "")
            break
    view_zoom = max(0.2, getattr(props, zoom_prop, 1.0))
    fit_orthographic_camera(
        camera,
        corners,
        margin=props.margin * view_zoom,
        res_x=props.resolution_x,
        res_y=props.resolution_y,
    )


def apply_drawing_render_settings(scene, props):
    scene.render.resolution_x = int(props.resolution_x)
    scene.render.resolution_y = int(props.resolution_y)
    force_white = bool(getattr(props, "force_white_background", False))
    fast_white = force_white and bool(getattr(props, "fast_white_background", True))
    transparent = bool(props.transparent_background) and not force_white
    if force_white:
        scene.render.film_transparent = False
    else:
        scene.render.film_transparent = transparent
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    scene.render.image_settings.compression = int(getattr(props, "png_compression", 6))

    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine
            break
        except Exception:
            pass

    try:
        scene.render.use_freestyle = bool(props.use_freestyle)
        bpy.context.view_layer.use_freestyle = bool(props.use_freestyle)
    except Exception:
        pass

    try:
        if force_white:
            if not scene.world:
                scene.world = bpy.data.worlds.new("BL_White_World")
            scene.world.use_nodes = False
            scene.world.color = (1, 1, 1)
        elif scene.world:
            scene.world.color = (1, 1, 1)
    except Exception:
        pass

    try:
        scene.display.shading.background_type = "WORLD"
        scene.display.shading.background_color = (1, 1, 1)
    except Exception:
        pass

    try:
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        scene.view_settings.exposure = 0
        scene.view_settings.gamma = 1
    except Exception:
        pass


def get_or_create_drawing_material():
    mat = bpy.data.materials.get("BL_Drawing_White_Material")
    if not mat:
        mat = bpy.data.materials.new("BL_Drawing_White_Material")

    mat.diffuse_color = (1, 1, 1, 1)

    # Use an emission material so drawing surfaces stay white even if the scene has poor lighting.
    try:
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        emission = nodes.new(type="ShaderNodeEmission")
        emission.inputs[0].default_value = (1, 1, 1, 1)
        emission.inputs[1].default_value = 1.0

        output = nodes.new(type="ShaderNodeOutputMaterial")
        links.new(emission.outputs[0], output.inputs[0])
    except Exception:
        pass

    return mat

def get_or_create_dimension_material():
    mat = bpy.data.materials.get("BL_Dimension_Black_Material")
    if mat:
        return mat
    mat = bpy.data.materials.new("BL_Dimension_Black_Material")
    mat.diffuse_color = (0, 0, 0, 1)
    return mat


def apply_material_override(objs):
    override_mat = get_or_create_drawing_material()
    restore_data = []
    for obj in objs:
        if obj.type != "MESH":
            continue
        restore_data.append((obj, list(obj.data.materials)))
        obj.data.materials.clear()
        obj.data.materials.append(override_mat)
    return restore_data


def restore_materials(restore_data):
    for obj, mats in restore_data:
        try:
            obj.data.materials.clear()
            for mat in mats:
                obj.data.materials.append(mat)
        except Exception:
            continue


def create_cut_cutter(context, objs, cut_height, keep_mode):
    corners = world_bbox_corners(objs)
    min_v, max_v = bbox_min_max(corners)
    pad = max((max_v - min_v).length * 0.25, 1.0)
    size_x = max(max_v.x - min_v.x + pad * 2, 1.0)
    size_y = max(max_v.y - min_v.y + pad * 2, 1.0)

    if keep_mode == "ABOVE":
        z_min = cut_height
        z_max = max(max_v.z + pad, cut_height + 0.01)
    else:
        z_min = min(min_v.z - pad, cut_height - 0.01)
        z_max = cut_height

    size_z = max(z_max - z_min, 0.01)
    center = Vector(((min_v.x + max_v.x) * 0.5, (min_v.y + max_v.y) * 0.5, (z_min + z_max) * 0.5))

    mesh = bpy.data.meshes.new("BL_TEMP_SECTION_CUTTER_MESH")
    verts = [
        (-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5),
        (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5),
    ]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    cutter = bpy.data.objects.new("BL_TEMP_SECTION_CUTTER", mesh)
    cutter.location = center
    cutter.dimensions = (size_x, size_y, size_z)
    coll = get_or_create_collection("Busy Layout Temp")
    coll.objects.link(cutter)
    context.view_layer.update()
    cutter.display_type = "WIRE"
    cutter.hide_render = True
    return cutter


def apply_section_cut(context, objs, props):
    if not props.use_section_cut:
        return [], None

    cutter = create_cut_cutter(context, objs, props.cut_height, props.cut_keep_mode)
    modifiers = []
    for obj in mesh_objects_for_boolean(objs):
        try:
            mod = obj.modifiers.new("BL_TEMP_SECTION_CUT", "BOOLEAN")
            mod.operation = "INTERSECT"
            mod.object = cutter
            try:
                mod.solver = props.boolean_solver
            except Exception:
                pass
            mod.show_render = True
            mod.show_viewport = True
            modifiers.append((obj, mod))
        except Exception:
            continue
    context.view_layer.update()
    return modifiers, cutter


def remove_section_cut(modifiers, cutter):
    for obj, mod in modifiers:
        try:
            obj.modifiers.remove(mod)
        except Exception:
            pass
    if cutter:
        try:
            mesh = cutter.data
            bpy.data.objects.remove(cutter, do_unlink=True)
            if mesh:
                bpy.data.meshes.remove(mesh, do_unlink=True)
        except Exception:
            pass


def should_apply_cut_to_view(props, view_key):
    if not props.use_section_cut:
        return False
    if props.section_cut_plan_only:
        return view_key == "TOP_PLAN"
    return True


def safe_filename(text):
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text)


def selected_view_specs(props):
    return [spec for spec in VIEW_SPECS if getattr(props, spec["prop"], False)]


def paper_size_mm(props):
    paper = PAPER_PRESETS.get(props.paper_size, PAPER_PRESETS["A3"])
    orientation = "landscape" if props.orientation == "LANDSCAPE" else "portrait"
    return paper[orientation]



def format_length(value, props):
    length = abs(value) * props.dim_unit_scale
    if props.dim_decimals <= 0:
        txt = f"{length:.0f}"
    else:
        txt = f"{length:.{int(props.dim_decimals)}f}"
    suffix = props.dim_suffix or ""
    return txt + suffix


def create_curve_polyline(name, points, bevel_depth, material):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 1
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = 0
    spl = curve.splines.new("POLY")
    spl.points.add(len(points) - 1)
    for p, co in zip(spl.points, points):
        p.co = (co.x, co.y, co.z, 1.0)
    obj = bpy.data.objects.new(name, curve)
    obj.data.materials.append(material)
    coll = get_or_create_collection("Busy Layout Dimensions")
    coll.objects.link(obj)
    obj["busy_layout_dimension"] = True
    return obj


def create_dim_text(name, text, location, size, material, rotation_z=0.0):
    font_curve = bpy.data.curves.new(name + "_DATA", "FONT")
    font_curve.body = text
    font_curve.align_x = "CENTER"
    font_curve.align_y = "CENTER"
    font_curve.size = size
    font_curve.extrude = 0.0
    obj = bpy.data.objects.new(name, font_curve)
    obj.location = location
    obj.rotation_euler = (0.0, 0.0, rotation_z)
    obj.data.materials.append(material)
    coll = get_or_create_collection("Busy Layout Dimensions")
    coll.objects.link(obj)
    obj["busy_layout_dimension"] = True
    return obj


def add_dimension_xy(name, p1, p2, offset_vec, props, label_override=""):
    mat = get_or_create_dimension_material()
    z = props.dim_z
    p1 = Vector((p1.x, p1.y, z))
    p2 = Vector((p2.x, p2.y, z))
    off = Vector((offset_vec.x, offset_vec.y, 0.0))
    a = p1
    b = p2
    a2 = p1 + off
    b2 = p2 + off
    direction = b2 - a2
    length = direction.length
    if length <= 0.0001:
        return []
    dir_n = direction.normalized()
    perp = Vector((-dir_n.y, dir_n.x, 0.0))
    tick = props.dim_tick_size
    line_thick = props.dim_line_thickness
    tick_a1 = a2 - perp * tick
    tick_a2 = a2 + perp * tick
    tick_b1 = b2 - perp * tick
    tick_b2 = b2 + perp * tick
    objs = []
    objs.append(create_curve_polyline(name + "_EXT_A", [a, a2], line_thick, mat))
    objs.append(create_curve_polyline(name + "_EXT_B", [b, b2], line_thick, mat))
    objs.append(create_curve_polyline(name + "_DIM_LINE", [a2, b2], line_thick, mat))
    objs.append(create_curve_polyline(name + "_TICK_A", [tick_a1, tick_a2], line_thick, mat))
    objs.append(create_curve_polyline(name + "_TICK_B", [tick_b1, tick_b2], line_thick, mat))
    label = label_override or format_length((p2 - p1).length, props)
    mid = (a2 + b2) * 0.5
    text_offset = perp * props.dim_text_offset
    rot = 0.0
    if abs(dir_n.y) > abs(dir_n.x):
        rot = 1.57079632679
    objs.append(create_dim_text(name + "_TEXT", label, mid + text_offset, props.dim_text_size, mat, rot))
    return objs


def delete_busy_dimensions():
    count = 0
    for obj in list(bpy.data.objects):
        if obj.get("busy_layout_dimension"):
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            try:
                if data and data.users == 0:
                    if data.__class__.__name__ == "Curve":
                        bpy.data.curves.remove(data)
            except Exception:
                pass
            count += 1
    return count


def write_html_sheet(output_dir, props, image_records):
    output_dir = Path(output_dir)
    sheet_path = output_dir / "busy_layout_sheet.html"
    page_w, page_h = paper_size_mm(props)
    orientation_css = "landscape" if props.orientation == "LANDSCAPE" else "portrait"
    paper_label = html.escape(props.paper_size)
    title = html.escape(props.project_title or "Busy Layout Sheet")
    client = html.escape(props.client_name or "-")
    project_no = html.escape(props.project_no or "-")
    drawing_no = html.escape(props.drawing_no or "-")
    sheet_date = html.escape(props.sheet_date or str(date.today()))
    scale_label = html.escape(scale_display_label(props))
    scale_mode_note = "Real Scale" if props.scale_mode == "REAL_SCALE" else "Auto Fit"
    note = html.escape(props.sheet_note or "")
    if props.use_section_cut:
        mode = "상부 제거 / Keep Below" if props.cut_keep_mode == "BELOW" else "하부 제거 / Keep Above"
        cut_note = html.escape(f"Section cut: {mode}, height {props.cut_height:g}")
    else:
        cut_note = "Section cut: Off"
    cols = max(1, min(int(props.sheet_columns), 4))

    cards = []
    for rec in image_records:
        label = html.escape(rec["label"])
        filename = html.escape(Path(rec["path"]).name)
        badge_html = "<em>CUT</em>" if rec.get("cut") else ""
        card_scale_label = html.escape(rec.get("scale_label", scale_label))
        cards.append(f'''
        <section class="view-card">
            <div class="view-head">
                <h2>{label} {badge_html}</h2>
                <span>Scale: {card_scale_label}</span>
            </div>
            <img src="{filename}" alt="{label}">
        </section>
        ''')

    content = f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
@page {{
    size: {paper_label} {orientation_css};
    margin: 10mm;
}}
* {{ box-sizing: border-box; }}
body {{
    font-family: Arial, "Malgun Gothic", sans-serif;
    margin: 0;
    background: #f0f0f0;
}}
.sheet {{
    width: {page_w}mm;
    min-height: {page_h}mm;
    margin: 0 auto;
    padding: 10mm;
    background: white;
    border: 1px solid #ccc;
}}
.title-block {{
    display: grid;
    grid-template-columns: 1fr 72mm;
    gap: 6mm;
    border-bottom: 0.4mm solid #111;
    padding-bottom: 4mm;
    margin-bottom: 6mm;
}}
.title-block h1 {{ margin: 0 0 2mm 0; font-size: 18pt; }}
.title-block .subtitle {{ font-size: 9pt; color: #333; }}
.meta-table {{ border-collapse: collapse; width: 100%; font-size: 8pt; }}
.meta-table th, .meta-table td {{ border: 0.2mm solid #111; padding: 1.2mm 1.5mm; text-align: left; }}
.meta-table th {{ width: 22mm; font-weight: 700; background: #f7f7f7; }}
.grid {{ display: grid; grid-template-columns: repeat({cols}, 1fr); gap: 6mm; }}
.view-card {{ border: 0.25mm solid #111; min-height: 96mm; padding: 3mm; break-inside: avoid; }}
.view-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 3mm; margin-bottom: 2mm; border-bottom: 0.2mm solid #999; padding-bottom: 1.5mm; }}
.view-head h2 {{ margin: 0; font-size: 10.5pt; }}
.view-head em {{ font-size: 7pt; font-style: normal; border: 0.2mm solid #111; padding: 0.3mm 1mm; margin-left: 1mm; }}
.view-head span {{ font-size: 7.5pt; color: #333; white-space: nowrap; }}
.view-card img {{ width: 100%; max-height: 108mm; object-fit: contain; display: block; }}
.note {{ margin-top: 5mm; font-size: 8pt; color: #333; border-top: 0.2mm solid #999; padding-top: 2mm; }}
@media print {{
    body {{ background: white; }}
    .sheet {{ margin: 0; border: none; }}
}}
</style>
</head>
<body>
<main class="sheet">
    <header class="title-block">
        <div>
            <h1>{title}</h1>
            <div class="subtitle">Generated by Blender Busy Layout MVP v0.8-dev</div>
        </div>
        <table class="meta-table">
            <tr><th>Client</th><td>{client}</td></tr>
            <tr><th>Project</th><td>{project_no}</td></tr>
            <tr><th>Drawing</th><td>{drawing_no}</td></tr>
            <tr><th>Date</th><td>{sheet_date}</td></tr>
            <tr><th>Paper</th><td>{paper_label} {orientation_css}</td></tr>
        </table>
    </header>
    <div class="grid">
        {''.join(cards)}
    </div>
    <p class="note">
        {note}<br>
        {cut_note}<br>
        Scale mode: {html.escape(scale_mode_note)}<br>
        Viewport: {props.viewport_width_mm:g}mm x {props.viewport_height_mm:g}mm<br>
        Safe margin: {getattr(props, "real_scale_safe_margin_mm", 0):g}mm<br>
        Model unit: {html.escape(model_unit_display(props))}<br>
        Drawing background: {"Fast white RGB" if getattr(props, "force_white_background", False) and getattr(props, "fast_white_background", True) else "Forced white" if getattr(props, "force_white_background", False) else "Scene/transparent"}<br>
        브라우저에서 열고 인쇄 &gt; PDF 저장으로 출력하세요. Real Scale 모드는 카메라 Orthographic Scale을 기준으로 한 MVP 축척 기능입니다.
    </p>
</main>
</body>
</html>
'''
    sheet_path.write_text(content, encoding="utf-8")
    return str(sheet_path)


class BL_Layout_Props(bpy.types.PropertyGroup):
    selected_only: bpy.props.BoolProperty(name="선택 오브젝트만 사용", default=False)
    margin: bpy.props.FloatProperty(name="기본 줌아웃", default=1.12, min=1.0, max=10.0, description="전체 도면뷰 공통 여백/줌아웃 배율입니다. 정투영 카메라는 거리 대신 Orthographic Scale로 화면 범위가 바뀝니다.")
    zoom_top: bpy.props.FloatProperty(name="평면 줌", default=1.35, min=0.2, max=20.0)
    zoom_front: bpy.props.FloatProperty(name="정면 줌", default=1.35, min=0.2, max=20.0)
    zoom_right: bpy.props.FloatProperty(name="우측 줌", default=1.35, min=0.2, max=20.0)
    zoom_left: bpy.props.FloatProperty(name="좌측 줌", default=1.35, min=0.2, max=20.0)
    zoom_back: bpy.props.FloatProperty(name="배면 줌", default=1.35, min=0.2, max=20.0)
    zoom_iso: bpy.props.FloatProperty(name="ISO 줌", default=2.0, min=0.2, max=20.0)
    resolution_x: bpy.props.IntProperty(name="렌더 가로", default=2480, min=512, max=10000)
    resolution_y: bpy.props.IntProperty(name="렌더 세로", default=1754, min=512, max=10000)
    transparent_background: bpy.props.BoolProperty(name="투명 배경", default=False)
    force_white_background: bpy.props.BoolProperty(
        name="강제 흰 배경",
        default=True,
        description="켜면 렌더 배경을 강제로 흰색으로 만들고 투명 배경보다 우선 적용합니다.",
    )
    fast_white_background: bpy.props.BoolProperty(
        name="빠른 흰 배경",
        default=True,
        description="켜면 느린 PNG 배경 후처리를 건너뛰고 RGB 흰 배경 PNG로 저장합니다.",
    )
    png_compression: bpy.props.IntProperty(name="PNG 압축", default=6, min=0, max=15)
    use_freestyle: bpy.props.BoolProperty(name="Freestyle 외곽선", default=True)
    material_override: bpy.props.BoolProperty(name="무광 흰색 재질로 임시 렌더", default=True)
    output_dir: bpy.props.StringProperty(name="출력 폴더", subtype="DIR_PATH", default="//busy_layout_output/")

    scale_mode: bpy.props.EnumProperty(
        name="축척 모드",
        items=[
            ("AUTO_FIT", "Auto Fit", "기존 방식처럼 모델이 화면에 들어오도록 자동 맞춤합니다."),
            ("REAL_SCALE", "Real Scale", "용지 뷰포트 크기와 축척 프리셋으로 카메라 Orthographic Scale을 계산합니다."),
        ],
        default="AUTO_FIT",
    )
    scale_preset: bpy.props.EnumProperty(
        name="축척 프리셋",
        items=[
            ("10", "1:10", ""),
            ("20", "1:20", ""),
            ("30", "1:30", ""),
            ("50", "1:50", ""),
            ("75", "1:75", ""),
            ("100", "1:100", ""),
            ("150", "1:150", ""),
            ("200", "1:200", ""),
            ("CUSTOM", "Custom", ""),
        ],
        default="50",
    )
    custom_scale_denominator: bpy.props.FloatProperty(name="Custom denominator", default=50.0, min=0.001)
    model_unit: bpy.props.EnumProperty(
        name="모델 단위",
        items=[
            ("METER", "Meter", "Blender 1 unit = 1m"),
            ("MILLIMETER", "Millimeter", "Blender 1 unit = 1mm"),
        ],
        default="METER",
    )
    viewport_width_mm: bpy.props.FloatProperty(name="뷰포트 폭 mm", default=180.0, min=1.0)
    viewport_height_mm: bpy.props.FloatProperty(name="뷰포트 높이 mm", default=120.0, min=1.0)
    real_scale_safe_margin_mm: bpy.props.FloatProperty(
        name="Real Scale safe margin mm",
        default=10.0,
        min=0.0,
        max=100.0,
        description="치수선과 외곽선이 잘리지 않도록 실제 뷰포트보다 넓게 렌더합니다. 0이면 선택 축척 그대로입니다.",
    )
    real_scale_margin_factor: bpy.props.FloatProperty(
        name="Real Scale margin factor",
        default=1.0,
        min=0.001,
        max=10.0,
        description="1.0이면 선택 축척 그대로입니다. 1.1은 10% 넓게 보이지만 실제 축척 표기는 adjusted로 표시됩니다.",
    )
    real_scale_iso_auto_fit: bpy.props.BoolProperty(
        name="ISO는 Auto Fit 유지",
        default=True,
        description="켜면 Real Scale 모드에서도 ISO 뷰는 실제 축척 대신 기존 Auto Fit 카메라 맞춤을 사용합니다.",
    )

    use_section_cut: bpy.props.BoolProperty(name="단면 컷 사용", default=False, description="렌더 중에 임시 Boolean 컷을 적용합니다. 원본 모델에는 적용하지 않고 렌더 후 제거합니다.")
    section_cut_plan_only: bpy.props.BoolProperty(name="평면도에만 컷 적용", default=True, description="켜면 TOP_PLAN 렌더에만 컷을 적용합니다.")
    cut_height: bpy.props.FloatProperty(name="컷 높이", default=1.2, description="Blender 씬 단위 기준 컷 높이입니다. 미터 단위 모델이면 1.2 = 1200mm입니다.")
    cut_keep_mode: bpy.props.EnumProperty(
        name="컷 방식",
        items=[("BELOW", "상부 제거", "컷 높이 아래쪽만 남깁니다. 평면도용 기본값입니다."), ("ABOVE", "하부 제거", "컷 높이 위쪽만 남깁니다.")],
        default="BELOW",
    )
    boolean_solver: bpy.props.EnumProperty(
        name="Boolean Solver",
        items=[("FAST", "Fast", "빠르지만 복잡한 메시에서 실패할 수 있습니다."), ("EXACT", "Exact", "느리지만 비교적 안정적입니다.")],
        default="FAST",
    )

    dim_z: bpy.props.FloatProperty(name="치수선 Z 높이", default=0.02)
    dim_offset: bpy.props.FloatProperty(name="외곽 치수선 거리", default=0.35)
    dim_line_thickness: bpy.props.FloatProperty(name="치수선 두께", default=0.006, min=0.0001, max=1.0)
    dim_tick_size: bpy.props.FloatProperty(name="치수 틱 크기", default=0.08, min=0.0001, max=10.0)
    dim_text_size: bpy.props.FloatProperty(name="치수 글자 크기", default=0.16, min=0.001, max=10.0)
    dim_text_offset: bpy.props.FloatProperty(name="치수 글자 거리", default=0.08, min=-10.0, max=10.0)
    dim_unit_scale: bpy.props.FloatProperty(name="치수 배율", default=1000.0, description="미터 모델에서 mm로 표기하려면 1000. 밀리미터 모델이면 1.")
    dim_suffix: bpy.props.StringProperty(name="치수 접미사", default="")
    dim_decimals: bpy.props.IntProperty(name="소수점", default=0, min=0, max=4)

    project_title: bpy.props.StringProperty(name="도면 제목", default="Interior Drawing Sheet")
    client_name: bpy.props.StringProperty(name="클라이언트", default="")
    project_no: bpy.props.StringProperty(name="프로젝트 번호", default="")
    drawing_no: bpy.props.StringProperty(name="도면 번호", default="A-001")
    sheet_date: bpy.props.StringProperty(name="날짜", default="", description="비워두면 오늘 날짜가 자동 입력됩니다.")
    scale_label: bpy.props.StringProperty(name="축척 표기", default="Auto Fit")
    sheet_note: bpy.props.StringProperty(name="비고", default="v0.7: 실제 축척 프리셋은 Orthographic Scale 기반 MVP 기능입니다. margin factor를 1.0이 아닌 값으로 쓰면 표기 축척보다 넓게 보입니다.")

    paper_size: bpy.props.EnumProperty(name="용지", items=[("A4", "A4", ""), ("A3", "A3", ""), ("A2", "A2", "")], default="A3")
    orientation: bpy.props.EnumProperty(name="방향", items=[("LANDSCAPE", "가로", ""), ("PORTRAIT", "세로", "")], default="LANDSCAPE")
    sheet_columns: bpy.props.IntProperty(name="시트 열 수", default=2, min=1, max=4)

    view_top: bpy.props.BoolProperty(name="평면", default=True)
    view_front: bpy.props.BoolProperty(name="정면", default=True)
    view_right: bpy.props.BoolProperty(name="우측", default=True)
    view_left: bpy.props.BoolProperty(name="좌측", default=False)
    view_back: bpy.props.BoolProperty(name="배면", default=False)
    view_iso: bpy.props.BoolProperty(name="ISO", default=True)


class BL_OT_setup_cameras(bpy.types.Operator):
    bl_idname = "busy_layout.setup_cameras"
    bl_label = "도면 카메라 생성/갱신"
    bl_description = "모델 기준으로 평면도, 입면도, 아이소뷰 정투영 카메라를 생성합니다."

    def execute(self, context):
        props = context.scene.busy_layout_props
        objs = drawing_objects(context, props.selected_only)
        if not objs:
            self.report({"ERROR"}, "카메라 기준으로 삼을 오브젝트가 없습니다.")
            return {"CANCELLED"}

        corners = world_bbox_corners(objs)
        center, diag = bbox_center_and_diag(corners)
        apply_drawing_render_settings(context.scene, props)

        for spec in VIEW_SPECS:
            cam = get_or_create_camera(spec["name"])
            cam["busy_layout_view"] = spec["key"]
            cam.data.type = "ORTHO"
            cam.data.clip_start = 0.001
            cam.data.clip_end = max(diag * 10, 10000.0)
            direction = spec["direction"].normalized()
            cam.location = center - direction * diag * 2.0
            look_at(cam, center)
            set_camera_ortho_scale(cam, corners, props)

        context.scene.camera = bpy.data.objects.get("BL_TOP_PLAN")
        self.report({"INFO"}, "Busy Layout 카메라를 생성/갱신했습니다.")
        return {"FINISHED"}


class BL_OT_set_camera(bpy.types.Operator):
    bl_idname = "busy_layout.set_camera"
    bl_label = "도면 카메라 선택"
    camera_name: bpy.props.StringProperty()

    def execute(self, context):
        cam = bpy.data.objects.get(self.camera_name)
        if not cam or cam.type != "CAMERA":
            self.report({"ERROR"}, f"{self.camera_name} 카메라를 찾을 수 없습니다.")
            return {"CANCELLED"}
        context.scene.camera = cam
        self.report({"INFO"}, f"활성 카메라: {cam.name}")
        return {"FINISHED"}



class BL_OT_add_bbox_dimensions(bpy.types.Operator):
    bl_idname = "busy_layout.add_bbox_dimensions"
    bl_label = "외곽 가로/세로 치수선 생성"
    bl_description = "선택 오브젝트 또는 전체 모델의 XY 외곽 가로/세로 치수선을 생성합니다."

    def execute(self, context):
        props = context.scene.busy_layout_props
        objs = drawing_objects(context, props.selected_only)
        if not objs:
            self.report({"ERROR"}, "치수선을 만들 오브젝트가 없습니다.")
            return {"CANCELLED"}
        corners = world_bbox_corners(objs)
        min_v, max_v = bbox_min_max(corners)
        off = props.dim_offset
        add_dimension_xy("BL_DIM_BBOX_X", Vector((min_v.x, min_v.y, props.dim_z)), Vector((max_v.x, min_v.y, props.dim_z)), Vector((0, -off, 0)), props)
        add_dimension_xy("BL_DIM_BBOX_Y", Vector((min_v.x, min_v.y, props.dim_z)), Vector((min_v.x, max_v.y, props.dim_z)), Vector((-off, 0, 0)), props)
        self.report({"INFO"}, "외곽 가로/세로 치수선을 생성했습니다.")
        return {"FINISHED"}


class BL_OT_add_two_object_dimension(bpy.types.Operator):
    bl_idname = "busy_layout.add_two_object_dimension"
    bl_label = "두 오브젝트 중심 치수선"
    bl_description = "선택한 두 오브젝트의 원점 사이 평면 치수선을 생성합니다."

    def execute(self, context):
        props = context.scene.busy_layout_props
        objs = [o for o in context.selected_objects if o.visible_get() and not o.name.startswith("BL_")]
        if len(objs) != 2:
            self.report({"ERROR"}, "오브젝트 2개를 선택해야 합니다.")
            return {"CANCELLED"}
        p1 = objs[0].matrix_world.translation
        p2 = objs[1].matrix_world.translation
        vec = Vector((p2.x - p1.x, p2.y - p1.y, 0.0))
        if vec.length <= 0.0001:
            self.report({"ERROR"}, "XY 평면에서 두 오브젝트 위치가 같습니다.")
            return {"CANCELLED"}
        dir_n = vec.normalized()
        perp = Vector((-dir_n.y, dir_n.x, 0.0))
        add_dimension_xy("BL_DIM_TWO_OBJECTS", p1, p2, perp * props.dim_offset, props)
        self.report({"INFO"}, "두 오브젝트 중심 치수선을 생성했습니다.")
        return {"FINISHED"}


class BL_OT_clear_dimensions(bpy.types.Operator):
    bl_idname = "busy_layout.clear_dimensions"
    bl_label = "Busy 치수선 삭제"
    bl_description = "Busy Layout이 만든 치수선과 치수 텍스트를 삭제합니다."

    def execute(self, context):
        count = delete_busy_dimensions()
        self.report({"INFO"}, f"치수선 {count}개를 삭제했습니다.")
        return {"FINISHED"}


class BL_OT_apply_fine_dimension_style(bpy.types.Operator):
    bl_idname = "busy_layout.apply_fine_dimension_style"
    bl_label = "Fine 치수선 재생성"
    bl_description = "얇은 도면용 치수선 값을 적용하고 외곽 치수선을 다시 생성합니다."

    def execute(self, context):
        props = context.scene.busy_layout_props
        props.dim_offset = 0.42
        props.dim_line_thickness = 0.0025
        props.dim_tick_size = 0.05
        props.dim_text_size = 0.10
        props.dim_text_offset = 0.08

        objs = drawing_objects(context, props.selected_only)
        if not objs:
            self.report({"ERROR"}, "치수선을 만들 오브젝트가 없습니다.")
            return {"CANCELLED"}

        delete_busy_dimensions()
        corners = world_bbox_corners(objs)
        min_v, max_v = bbox_min_max(corners)
        off = props.dim_offset
        add_dimension_xy("BL_DIM_BBOX_X", Vector((min_v.x, min_v.y, props.dim_z)), Vector((max_v.x, min_v.y, props.dim_z)), Vector((0, -off, 0)), props)
        add_dimension_xy("BL_DIM_BBOX_Y", Vector((min_v.x, min_v.y, props.dim_z)), Vector((min_v.x, max_v.y, props.dim_z)), Vector((-off, 0, 0)), props)
        self.report({"INFO"}, "Fine 스타일로 외곽 치수선을 다시 생성했습니다.")
        return {"FINISHED"}


class BL_OT_apply_draft_render_preset(bpy.types.Operator):
    bl_idname = "busy_layout.apply_draft_render_preset"
    bl_label = "Draft 렌더 프리셋"
    bl_description = "빠른 테스트용 해상도와 PNG 설정을 적용합니다."

    def execute(self, context):
        props = context.scene.busy_layout_props
        props.resolution_x = 1280
        props.resolution_y = 905
        props.fast_white_background = True
        props.png_compression = 3
        self.report({"INFO"}, "Draft 렌더 프리셋을 적용했습니다.")
        return {"FINISHED"}


class BL_OT_apply_final_render_preset(bpy.types.Operator):
    bl_idname = "busy_layout.apply_final_render_preset"
    bl_label = "Final 렌더 프리셋"
    bl_description = "최종 출력용 A3급 해상도와 PNG 설정을 적용합니다."

    def execute(self, context):
        props = context.scene.busy_layout_props
        props.resolution_x = 2480
        props.resolution_y = 1754
        props.fast_white_background = True
        props.png_compression = 6
        self.report({"INFO"}, "Final 렌더 프리셋을 적용했습니다.")
        return {"FINISHED"}


class BL_OT_render_active(bpy.types.Operator):
    bl_idname = "busy_layout.render_active"
    bl_label = "현재 도면뷰 렌더"
    bl_description = "현재 활성 카메라를 PNG로 렌더합니다."

    def execute(self, context):
        props = context.scene.busy_layout_props
        scene = context.scene
        if not scene.camera:
            self.report({"ERROR"}, "활성 카메라가 없습니다.")
            return {"CANCELLED"}

        apply_drawing_render_settings(scene, props)
        out_dir = Path(bpy.path.abspath(props.output_dir))
        out_dir.mkdir(parents=True, exist_ok=True)
        objs = drawing_objects(context, props.selected_only)
        corners = world_bbox_corners(objs)
        restore_data = apply_material_override(objs) if props.material_override else []
        cut_mods = []
        cutter = None
        view_key = scene.camera.get("busy_layout_view", "") if scene.camera else ""

        try:
            if view_key:
                set_camera_ortho_scale(scene.camera, corners, props)
            if should_apply_cut_to_view(props, view_key):
                cut_mods, cutter = apply_section_cut(context, objs, props)
            filename = safe_filename(scene.camera.name) + ".png"
            path = out_dir / filename
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            if getattr(props, "force_white_background", False) and not getattr(props, "fast_white_background", True):
                png_force_border_background_white(path)
        finally:
            if cut_mods or cutter:
                remove_section_cut(cut_mods, cutter)
            if restore_data:
                restore_materials(restore_data)

        self.report({"INFO"}, f"렌더 완료: {path}")
        return {"FINISHED"}


class BL_OT_render_all(bpy.types.Operator):
    bl_idname = "busy_layout.render_all"
    bl_label = "선택 도면뷰 렌더 + 시트 생성"
    bl_description = "선택한 도면뷰를 렌더하고 PDF 저장용 HTML 시트를 만듭니다."

    def execute(self, context):
        props = context.scene.busy_layout_props
        scene = context.scene
        apply_drawing_render_settings(scene, props)
        out_dir = Path(bpy.path.abspath(props.output_dir))
        out_dir.mkdir(parents=True, exist_ok=True)

        specs = selected_view_specs(props)
        if not specs:
            self.report({"ERROR"}, "렌더할 뷰가 선택되지 않았습니다.")
            return {"CANCELLED"}

        objs = drawing_objects(context, props.selected_only)
        corners = world_bbox_corners(objs)
        restore_data = apply_material_override(objs) if props.material_override else []
        image_records = []

        try:
            for spec in specs:
                cam = bpy.data.objects.get(spec["name"])
                if not cam or cam.type != "CAMERA":
                    self.report({"WARNING"}, f"{spec['name']} 카메라가 없어 건너뜁니다.")
                    continue
                scene.camera = cam
                set_camera_ortho_scale(cam, corners, props)
                cut_mods = []
                cutter = None
                cut_applied = should_apply_cut_to_view(props, spec["key"])
                try:
                    if cut_applied:
                        cut_mods, cutter = apply_section_cut(context, objs, props)
                    filename = safe_filename(spec["name"]) + ".png"
                    path = out_dir / filename
                    scene.render.filepath = str(path)
                    bpy.ops.render.render(write_still=True)
                    if getattr(props, "force_white_background", False) and not getattr(props, "fast_white_background", True):
                        png_force_border_background_white(path)
                    image_records.append({
                        "label": spec["label"],
                        "path": str(path),
                        "cut": bool(cut_applied),
                        "scale_label": view_scale_display_label(props, spec["key"]),
                    })
                finally:
                    if cut_mods or cutter:
                        remove_section_cut(cut_mods, cutter)
        finally:
            if restore_data:
                restore_materials(restore_data)

        if not image_records:
            self.report({"ERROR"}, "렌더할 Busy Layout 카메라가 없습니다. 먼저 카메라를 생성하세요.")
            return {"CANCELLED"}

        sheet_path = write_html_sheet(out_dir, props, image_records)
        self.report({"INFO"}, f"시트 생성 완료: {sheet_path}")
        return {"FINISHED"}


class BL_OT_dev_reload_scripts(bpy.types.Operator):
    bl_idname = "busy_layout.dev_reload_scripts"
    bl_label = "Dev Reload Scripts"
    bl_description = "개발 중 Blender를 재시작하지 않고 Python 스크립트와 애드온을 다시 로드합니다."

    def execute(self, context):
        try:
            bpy.ops.script.reload()
        except Exception as exc:
            self.report({"ERROR"}, f"Reload Scripts 실패: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, "Blender scripts reloaded.")
        return {"FINISHED"}


class BL_PT_panel(bpy.types.Panel):
    bl_label = "Busy Layout MVP"
    bl_idname = "BL_PT_busy_layout_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Busy Layout"

    def draw(self, context):
        layout = self.layout
        props = context.scene.busy_layout_props

        box = layout.box()
        box.label(text="1. 기준/렌더 설정")
        box.prop(props, "selected_only")
        box.prop(props, "margin")
        box.label(text="뷰별 줌아웃 배율")
        row = box.row(align=True)
        row.prop(props, "zoom_top")
        row.prop(props, "zoom_front")
        row.prop(props, "zoom_right")
        row = box.row(align=True)
        row.prop(props, "zoom_left")
        row.prop(props, "zoom_back")
        row.prop(props, "zoom_iso")
        row = box.row(align=True)
        row.prop(props, "resolution_x")
        row.prop(props, "resolution_y")
        box.prop(props, "use_freestyle")
        box.prop(props, "force_white_background")
        box.prop(props, "fast_white_background")
        box.prop(props, "png_compression")
        box.prop(props, "material_override")
        box.prop(props, "transparent_background")
        box.prop(props, "output_dir")
        row = box.row(align=True)
        row.operator("busy_layout.apply_draft_render_preset", icon="SHADING_RENDERED")
        row.operator("busy_layout.apply_final_render_preset", icon="RENDER_STILL")

        box = layout.box()
        box.label(text="2. 단면 컷")
        box.prop(props, "use_section_cut")
        box.prop(props, "section_cut_plan_only")
        box.prop(props, "cut_height")
        box.prop(props, "cut_keep_mode")
        box.prop(props, "boolean_solver")

        box = layout.box()
        box.label(text="3. 치수선 v0.4")
        row = box.row(align=True)
        row.prop(props, "dim_z")
        row.prop(props, "dim_offset")
        row = box.row(align=True)
        row.prop(props, "dim_line_thickness")
        row.prop(props, "dim_tick_size")
        row = box.row(align=True)
        row.prop(props, "dim_text_size")
        row.prop(props, "dim_text_offset")
        row = box.row(align=True)
        row.prop(props, "dim_unit_scale")
        row.prop(props, "dim_decimals")
        box.prop(props, "dim_suffix")
        box.operator("busy_layout.apply_fine_dimension_style", icon="GREASEPENCIL")
        box.operator("busy_layout.add_bbox_dimensions", icon="EMPTY_ARROWS")
        box.operator("busy_layout.add_two_object_dimension", icon="DRIVER_DISTANCE")
        box.operator("busy_layout.clear_dimensions", icon="TRASH")

        box = layout.box()
        box.label(text="4. 도면 정보")
        box.prop(props, "project_title")
        box.prop(props, "client_name")
        box.prop(props, "project_no")
        box.prop(props, "drawing_no")
        box.prop(props, "sheet_date")
        box.prop(props, "sheet_note")

        box = layout.box()
        box.label(text="5. 시트")
        row = box.row(align=True)
        row.prop(props, "paper_size")
        row.prop(props, "orientation")
        box.prop(props, "sheet_columns")

        box = layout.box()
        box.label(text="6. 축척 v0.8")
        box.prop(props, "scale_mode")
        if props.scale_mode == "REAL_SCALE":
            box.prop(props, "scale_preset")
            if props.scale_preset == "CUSTOM":
                box.prop(props, "custom_scale_denominator")
            box.prop(props, "model_unit")
            row = box.row(align=True)
            row.prop(props, "viewport_width_mm")
            row.prop(props, "viewport_height_mm")
            box.prop(props, "real_scale_safe_margin_mm")
            box.prop(props, "real_scale_margin_factor")
            box.prop(props, "real_scale_iso_auto_fit")
            box.label(text=f"현재 표기: Scale: {scale_display_label(props)}")
        else:
            box.label(text="현재 표기: Scale: Auto Fit")

        box = layout.box()
        box.label(text="7. 출력할 뷰")
        row = box.row(align=True)
        row.prop(props, "view_top")
        row.prop(props, "view_front")
        row.prop(props, "view_right")
        row = box.row(align=True)
        row.prop(props, "view_left")
        row.prop(props, "view_back")
        row.prop(props, "view_iso")

        layout.separator()
        layout.operator("busy_layout.setup_cameras", icon="CAMERA_DATA")

        layout.separator()
        row = layout.row(align=True)
        op = row.operator("busy_layout.set_camera", text="평면")
        op.camera_name = "BL_TOP_PLAN"
        op = row.operator("busy_layout.set_camera", text="정면")
        op.camera_name = "BL_FRONT_ELEVATION"
        op = row.operator("busy_layout.set_camera", text="우측")
        op.camera_name = "BL_RIGHT_ELEVATION"

        row = layout.row(align=True)
        op = row.operator("busy_layout.set_camera", text="좌측")
        op.camera_name = "BL_LEFT_ELEVATION"
        op = row.operator("busy_layout.set_camera", text="배면")
        op.camera_name = "BL_BACK_ELEVATION"
        op = row.operator("busy_layout.set_camera", text="ISO")
        op.camera_name = "BL_ISO_VIEW"

        layout.separator()
        layout.operator("busy_layout.render_active", icon="RENDER_STILL")
        layout.operator("busy_layout.render_all", icon="OUTPUT")

        layout.separator()
        layout.operator("busy_layout.dev_reload_scripts", icon="FILE_REFRESH")


classes = (
    BL_Layout_Props,
    BL_OT_setup_cameras,
    BL_OT_set_camera,
    BL_OT_add_bbox_dimensions,
    BL_OT_add_two_object_dimension,
    BL_OT_clear_dimensions,
    BL_OT_apply_fine_dimension_style,
    BL_OT_apply_draft_render_preset,
    BL_OT_apply_final_render_preset,
    BL_OT_render_active,
    BL_OT_render_all,
    BL_OT_dev_reload_scripts,
    BL_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.busy_layout_props = bpy.props.PointerProperty(type=BL_Layout_Props)


def unregister():
    if hasattr(bpy.types.Scene, "busy_layout_props"):
        del bpy.types.Scene.busy_layout_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
