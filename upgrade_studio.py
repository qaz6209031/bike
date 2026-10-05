"""Cycles studio presentation for the existing Canyon Endurace model.

Upgrade without rebuilding geometry:
  Blender --background endurace_cf_slx_7_axs_M.blend --python upgrade_studio.py -- --render
Quick lighting proof:
  ... -- --render --preview
Re-render an already upgraded file:
  Blender --background endurace_cf_slx_7_axs_M_studio.blend --python upgrade_studio.py -- --render-only

The external HDRI is Poly Haven's Studio Small 09 (Sergej Majboroda, CC0).
All images, including the HDRI and existing decals, are packed into the saved blend.
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

OUT = os.path.dirname(os.path.abspath(__file__))
HDRI = "studio_small_09_2k.hdr"
STUDIO_COLLECTION = "Studio | Cycles"


def principled(material):
    if material.node_tree is None:
        material.use_nodes = True
    return next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def set_inputs(shader, **values):
    for name, value in values.items():
        if name in shader.inputs:
            shader.inputs[name].default_value = value


def math_node(nt, operation, *values, label=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = operation
    n.label = label or operation.title()
    for socket, value in zip(n.inputs, values):
        if isinstance(value, (int, float)):
            socket.default_value = value
        else:
            nt.links.new(value, socket)
    return n.outputs[0]


def lerp(nt, a, b, fac):
    return math_node(nt, "ADD", math_node(nt, "MULTIPLY", a,
                     math_node(nt, "SUBTRACT", 1, fac)),
                     math_node(nt, "MULTIPLY", b, fac))


def micro_surface(material, *, scale, distance, strength, roughness, stretch=None):
    """Add fine grain after the existing tread/wrap normal, preserving that detail."""
    nt = material.node_tree
    b = principled(material)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.label = "Local coordinates | metres"
    vector = tc.outputs["Object"]
    if stretch:
        mapping = nt.nodes.new("ShaderNodeVectorMath")
        mapping.operation = "MULTIPLY"
        nt.links.new(vector, mapping.inputs[0])
        mapping.inputs[1].default_value = stretch
        vector = mapping.outputs[0]
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.label = "Surface microstructure"
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 2.0
    noise.inputs["Roughness"].default_value = 0.65
    nt.links.new(vector, noise.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.label = f"Microscopic relief | {distance * 1e6:.0f} microns"
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = distance
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    if b.inputs["Normal"].is_linked:
        upstream = b.inputs["Normal"].links[0].from_socket
        nt.links.new(upstream, bump.inputs["Normal"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.label = "Fine roughness variation"
    rough.inputs["To Min"].default_value = roughness[0]
    rough.inputs["To Max"].default_value = roughness[1]
    nt.links.new(noise.outputs["Fac"], rough.inputs["Value"])
    nt.links.new(rough.outputs[0], b.inputs["Roughness"])


def unwrap_carbon_ribbons(scene):
    """Metric UVs for the four-vertex rings emitted by build_endurace.ribbon.

    U is actual distance along the strip; V is distance around its perimeter.
    Separate each perimeter seam rather than stretching one UV square per object.
    Does not alter any vertices, faces, transforms, or existing modelling detail.
    """
    count = 0
    for ob in scene.objects:
        if ob.type != "MESH" or not any(m and m.name == "Carbon Weave" for m in ob.data.materials):
            continue
        me = ob.data
        if len(me.vertices) % 4:
            raise ValueError(f"Unexpected carbon ribbon topology: {ob.name}")
        rings = [[me.vertices[i + k].co.copy() for k in range(4)]
                 for i in range(0, len(me.vertices), 4)]
        centres = [sum(ring, Vector()) / 4 for ring in rings]
        arc = [0.0]
        for a, b in zip(centres, centres[1:]):
            arc.append(arc[-1] + (b - a).length)
        perimeter = []
        for ring in rings:
            p = [0.0]
            for k in range(4):
                p.append(p[-1] + (ring[(k + 1) % 4] - ring[k]).length)
            perimeter.append(p)
        uv = me.uv_layers.get("CarbonMetricUV") or me.uv_layers.new(name="CarbonMetricUV")
        for face in me.polygons:
            corners = {me.loops[li].vertex_index % 4 for li in face.loop_indices}
            wrap_seam = corners == {0, 3}
            for li in face.loop_indices:
                vi = me.loops[li].vertex_index
                ri, corner = divmod(vi, 4)
                uv.data[li].uv = (arc[ri], perimeter[ri][4 if wrap_seam and corner == 0 else corner])
        me.uv_layers.active = uv
        uv.active_render = True
        count += 1
    print(f"[studio] Metric carbon UVs: {count} cage strips")


def carbon_twill(material):
    """Procedural 3K-style 2x2 twill: two orthogonal fibre lobes under clear resin.

    2.5 mm tow width; the 10 mm repeat contains four tows. Microscopic strands
    are represented by a bump signal, not a printed checkerboard colour map.
    """
    nt = material.node_tree
    nt.nodes.clear()
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "CarbonMetricUV"
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.label = "45 degree twill | 2.5 mm tow"
    mapping.inputs["Scale"].default_value = (400, 400, 400)
    mapping.inputs["Rotation"].default_value.z = math.radians(45)
    nt.links.new(uv.outputs[0], mapping.inputs["Vector"])
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(mapping.outputs[0], sep.inputs[0])
    x, y = sep.outputs["X"], sep.outputs["Y"]
    phase = math_node(nt, "FLOORED_MODULO",
                      math_node(nt, "SUBTRACT", math_node(nt, "FLOOR", x),
                                math_node(nt, "FLOOR", y)), 4)
    over = math_node(nt, "LESS_THAN", phase, 2, label="2 over / 2 under twill")
    cross_x = math_node(nt, "SINE", math_node(nt, "MULTIPLY", math_node(nt, "FRACT", x), math.pi))
    cross_y = math_node(nt, "SINE", math_node(nt, "MULTIPLY", math_node(nt, "FRACT", y), math.pi))
    bundle = lerp(nt, cross_y, cross_x, over)
    strands_x = math_node(nt, "SINE", math_node(nt, "MULTIPLY", x, math.tau * 48))
    strands_y = math_node(nt, "SINE", math_node(nt, "MULTIPLY", y, math.tau * 48))
    strands = lerp(nt, strands_y, strands_x, over)
    height = math_node(nt, "ADD", math_node(nt, "MULTIPLY", bundle, 0.8),
                       math_node(nt, "MULTIPLY", strands, 0.035))
    bump = nt.nodes.new("ShaderNodeBump")
    bump.label = "Woven fibres beneath smooth resin"
    bump.inputs["Strength"].default_value = 0.32
    bump.inputs["Distance"].default_value = 0.000022
    nt.links.new(height, bump.inputs["Height"])
    colour = nt.nodes.new("ShaderNodeValToRGB")
    colour.label = "Carbon fibres | subtle tonal variation"
    colour.color_ramp.elements[0].color = (0.008, 0.009, 0.010, 1)
    colour.color_ramp.elements[1].color = (0.022, 0.024, 0.027, 1)
    nt.links.new(bundle, colour.inputs[0])
    tangent = nt.nodes.new("ShaderNodeTangent")
    tangent.direction_type = "UV_MAP"
    tangent.uv_map = "CarbonMetricUV"
    shaders = []
    for name, angle in (("Warp fibre | along tow", 0.125), ("Weft fibre | across tow", 0.375)):
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        b.label = name
        set_inputs(b, **{"Roughness": 0.30, "Metallic": 0.0, "IOR": 1.62,
                         "Anisotropic": 0.72, "Anisotropic Rotation": angle,
                         "Coat Weight": 1.0, "Coat Roughness": 0.105, "Coat IOR": 1.5})
        nt.links.new(colour.outputs[0], b.inputs["Base Color"])
        nt.links.new(tangent.outputs[0], b.inputs["Tangent"])
        nt.links.new(bump.outputs[0], b.inputs["Normal"])
        shaders.append(b)
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(over, mix.inputs[0])
    for i, b in enumerate(shaders):
        nt.links.new(b.outputs[0], mix.inputs[i + 1])
    output = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(mix.outputs[0], output.inputs["Surface"])
    material.diffuse_color = (0.018, 0.020, 0.022, 1)
    material["weave"] = "Procedural 3K-style 2x2 twill; 2.5 mm tows; orthogonal fibre highlights"


def upgrade_materials(scene):
    white = bpy.data.materials.get("Crystal White")
    if white:
        b = principled(white)
        set_inputs(b, **{"Base Color": (0.86, 0.865, 0.85, 1), "Metallic": 0,
                         "Roughness": 0.24, "IOR": 1.5, "Coat Weight": 1,
                         "Coat Roughness": 0.065, "Coat IOR": 1.5})
        # Very shallow paint texture; clear coat stays optically smooth.
        micro_surface(white, scale=5000, distance=0.000012, strength=0.025,
                      roughness=(0.22, 0.26))
    carbon = bpy.data.materials.get("Carbon Black")
    if carbon:
        set_inputs(principled(carbon), **{"Base Color": (0.012, 0.014, 0.017, 1),
                    "Roughness": 0.30, "Coat Weight": 0.65, "Coat Roughness": 0.16})
    woven = bpy.data.materials.get("Carbon Weave")
    if woven:
        unwrap_carbon_ribbons(scene)
        carbon_twill(woven)

    # Existing chevrons, shoulder tread, wraps and prints are retained.
    rubber = {
        "Tire Rubber": (6200, 0.000045, 0.20, (0.58, 0.70)),
        "Hood Rubber": (7200, 0.000040, 0.24, (0.61, 0.72)),
        "Bar Tape": (8500, 0.000045, 0.22, (0.58, 0.69)),
        "Saddle Microfibre": (9500, 0.000028, 0.18, (0.48, 0.58)),
        "Saddle Side Panel": (7800, 0.000024, 0.16, (0.57, 0.67)),
        "Pedal Resin": (6500, 0.000018, 0.12, (0.38, 0.47)),
        "FD Arm Matte": (6800, 0.000018, 0.14, (0.65, 0.74)),
    }
    for name, (scale, depth, strength, rough) in rubber.items():
        m = bpy.data.materials.get(name)
        if not m:
            continue
        for node in m.node_tree.nodes:
            if node.type == "BUMP" and name in ("Hood Rubber", "Bar Tape"):
                node.inputs["Distance"].default_value = 0.00028
                node.inputs["Strength"].default_value = 0.55
        set_inputs(principled(m), **{"Specular IOR Level": 0.32})
        micro_surface(m, scale=scale, distance=depth, strength=strength, roughness=rough)

    brushed = {
        "Steel": (0.56, 0.57, 0.59, 0.27),
        "Rotor Steel": (0.62, 0.63, 0.65, 0.32),
        "Cassette Steel": (0.65, 0.66, 0.68, 0.23),
        "Chain Steel": (0.52, 0.53, 0.55, 0.28),
        "Pedal Plate": (0.56, 0.57, 0.59, 0.30),
        "AXS Silver Grey": (0.40, 0.41, 0.43, 0.34),
        "FD Cage Polished": (0.72, 0.73, 0.76, 0.19),
    }
    for name, (r, g, bl, rough) in brushed.items():
        m = bpy.data.materials.get(name)
        if not m:
            continue
        b = principled(m)
        set_inputs(b, **{"Base Color": (r, g, bl, 1), "Metallic": 1.0,
                         "Anisotropic": 0.55, "Coat Weight": 0.0})
        tangent = m.node_tree.nodes.new("ShaderNodeTangent")
        tangent.direction_type = "RADIAL"
        tangent.axis = "Z"
        m.node_tree.links.new(tangent.outputs[0], b.inputs["Tangent"])
        micro_surface(m, scale=1, distance=0.000006, strength=0.12,
                      roughness=(rough - 0.025, rough + 0.025), stretch=(80, 22000, 22000))

    for name, rough in (("Dark Metal", 0.30), ("DT Swiss Hub Black", 0.29), ("Chainring Black", 0.31)):
        m = bpy.data.materials.get(name)
        if m:
            set_inputs(principled(m), **{"Base Color": (0.025, 0.029, 0.035, 1),
                       "Metallic": 1.0, "Anisotropic": 0.35,
                       "Coat Weight": 0.25, "Coat Roughness": 0.23})
            micro_surface(m, scale=7600, distance=0.000004, strength=0.10,
                          roughness=(rough - 0.03, rough + 0.03))
    lever = bpy.data.materials.get("Rival Lever Gloss")
    if lever:
        set_inputs(principled(lever), **{"Roughness": 0.18, "Metallic": 0.65,
                                        "Coat Weight": 1, "Coat Roughness": 0.075})


def collection_for(scene):
    old = bpy.data.collections.get(STUDIO_COLLECTION)
    if old:
        for ob in list(old.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.collections.remove(old)
    col = bpy.data.collections.new(STUDIO_COLLECTION)
    scene.collection.children.link(col)
    return col


def link_object(col, ob):
    col.objects.link(ob)
    return ob


def studio_backdrop(col, centre_x, ground_z):
    """An infinity cove surrounding the bike, so either side has no floor edge."""
    radius, curve_radius, segments = 5.0, 2.0, 128
    rings = [(radius, ground_z)]
    for k in range(1, 25):
        a = (math.pi / 2) * k / 24
        rings.append((radius + curve_radius * math.sin(a),
                      ground_z + curve_radius * (1 - math.cos(a))))
    rings.append((radius + curve_radius, ground_z + 10))
    verts = [(centre_x + r * math.cos(math.tau * j / segments),
              r * math.sin(math.tau * j / segments), z)
             for r, z in rings for j in range(segments)]
    faces = [tuple(range(segments))]
    for i in range(len(rings) - 1):
        for j in range(segments):
            a, b = i * segments + j, i * segments + (j + 1) % segments
            faces.append((a, a + segments, b + segments, b))
    me = bpy.data.meshes.new("Seamless infinity cove")
    me.from_pydata(verts, [], faces)
    me.update()
    ob = link_object(col, bpy.data.objects.new("Studio | seamless backdrop", me))
    ob.hide_select = True
    for p in me.polygons:
        p.use_smooth = p.index > 0
    mat = bpy.data.materials.get("Studio | neutral backdrop") or bpy.data.materials.new("Studio | neutral backdrop")
    b = principled(mat)
    set_inputs(b, **{"Base Color": (0.30, 0.315, 0.335, 1), "Roughness": 0.86,
                    "Specular IOR Level": 0.18})
    me.materials.append(mat)
    return ob


def area_light(col, name, loc, target, energy, size, size_y, colour=(1, 1, 1)):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = "RECTANGLE"
    data.size, data.size_y = size, size_y
    data.color = colour
    ob = link_object(col, bpy.data.objects.new(name, data))
    ob.location = loc
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()
    return ob


def setup_world(scene, out):
    path = os.path.join(out, HDRI)
    packed_hdri = bpy.data.images.get(HDRI)
    if not os.path.isfile(path) and not (packed_hdri and packed_hdri.packed_file):
        raise FileNotFoundError(f"Missing CC0 studio HDRI: {path}. See STUDIO.md for the download URL.")
    world = bpy.data.worlds.get("Studio | HDRI") or bpy.data.worlds.new("Studio | HDRI")
    scene.world = world
    if world.node_tree is None:
        world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value.z = math.radians(115)
    nt.links.new(tc.outputs["Generated"], mapping.inputs["Vector"])
    tex = nt.nodes.new("ShaderNodeTexEnvironment")
    tex.label = "Poly Haven | Studio Small 09 | CC0"
    tex.image = packed_hdri or bpy.data.images.load(path, check_existing=True)
    tex.image.pack()
    nt.links.new(mapping.outputs[0], tex.inputs["Vector"])
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.28
    nt.links.new(tex.outputs[0], bg.inputs["Color"])
    output = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg.outputs[0], output.inputs["Surface"])
    world["source"] = "https://polyhaven.com/a/studio_small_09"
    world["license"] = "CC0; Sergej Majboroda"


def configure_gpu(scene):
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "METAL" if sys.platform == "darwin" else "CUDA"
        prefs.get_devices()
        devices = [d for d in prefs.devices if d.type != "CPU"]
        for d in prefs.devices:
            d.use = d in devices
        scene.cycles.device = "GPU" if devices else "CPU"
        print(f"[studio] Render device: {scene.cycles.device}; {[d.name for d in devices]}")
    except (TypeError, RuntimeError):
        scene.cycles.device = "CPU"
        print("[studio] Render device: CPU")


def camera(col, name, loc, target, lens, fstop):
    data = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    ob = bpy.data.objects.get(name)
    if not ob:
        ob = link_object(col, bpy.data.objects.new(name, data))
    ob.location = loc
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()
    data.type = "PERSP"
    data.lens = lens
    data.sensor_width = 36
    data.clip_start, data.clip_end = 0.01, 100
    focus = link_object(col, bpy.data.objects.new(name + " | focus", None))
    focus.location = target
    focus.empty_display_size = 0.03
    focus.hide_render = True
    data.dof.use_dof = True
    data.dof.focus_object = focus
    data.dof.aperture_fstop = fstop
    data.dof.aperture_blades = 9
    return ob


def configure_studio(scene, out=OUT, size="M", samples=160):
    # Idempotence matters when re-running on a saved studio file: do not stack grain nodes.
    if not scene.get("studio_materials_version"):
        upgrade_materials(scene)
        scene["studio_materials_version"] = 1
    existing_side = bpy.data.objects.get("Cam_Side")
    centre_x = existing_side.location.x if existing_side else 0.0931
    ground_z = -0.269
    for ob in list(scene.objects):
        if ob.type == "MESH" and not ob.parent and any(m and m.name == "Floor" for m in ob.data.materials):
            ground_z = ob.location.z
            bpy.data.objects.remove(ob, do_unlink=True)
        elif ob.type == "LIGHT" and ob.name in ("Sun", "Key", "Key_Left"):
            bpy.data.objects.remove(ob, do_unlink=True)
    col = collection_for(scene)
    studio_backdrop(col, centre_x, ground_z)
    setup_world(scene, out)
    target = (centre_x, 0, 0.28)
    area_light(col, "Studio | key softbox", (0.55, -2.0, 2.5), target, 520, 3.0, 1.5)
    area_light(col, "Studio | fill softbox", (-1.1, 2.0, 1.6), target, 240, 2.5, 2.0)
    area_light(col, "Studio | overhead strip", (0.1, 0.25, 2.6), target, 280, 3.0, 0.65)
    area_light(col, "Studio | rim strip", (0.5, 1.8, 1.2), target, 190, 1.8, 0.45)
    centre = Vector((centre_x, 0, 0.32))
    side = camera(col, "Cam_Side", centre + Vector((0, -4.2, 0.03)), centre, 72, 16)
    camera(col, "Cam_Left", centre + Vector((0, 4.2, 0.03)), centre, 72, 16)
    hero = camera(col, "Cam_ThreeQuarter", centre + Vector((1.9, -3.5, 0.58)), centre, 67, 11)
    camera(col, "Cam_Studio_Materials", (centre_x + 0.20, -1.1, 0.52),
           (centre_x + 0.01, -0.01, 0.26), 78, 8)
    camera(col, "Cam_Studio_Cockpit", (1.00, -0.82, 1.04), (0.46, -0.04, 0.58), 80, 8)
    scene.camera = hero
    r = scene.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y, r.resolution_percentage = 1800, 1125, 100
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    r.image_settings.color_depth = "8"
    r.film_transparent = False
    scene.cycles.samples = samples
    scene.cycles.preview_samples = 32
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.015
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.max_bounces = 10
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 6
    scene.cycles.transparent_max_bounces = 12
    scene.cycles.sample_clamp_indirect = 8
    configure_gpu(scene)
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene["studio_size"] = size
    scene["studio_hdri_source"] = "https://polyhaven.com/a/studio_small_09"
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                space = area.spaces.active
                space.shading.type = "MATERIAL"
                space.shading.use_scene_world = True
                space.shading.use_scene_lights = True
                space.overlay.show_overlays = False
                space.clip_start = 0.001
                space.region_3d.view_perspective = "CAMERA"
    bpy.ops.file.pack_all()
    print(f"[studio] Cycles / {samples} samples / AgX / HDRI / layered finishes / DOF")
    return side, hero


def render_views(scene, out=OUT, size="M", preview=False, views=("34", "side", "materials", "cockpit")):
    cameras = {"34": "Cam_ThreeQuarter", "side": "Cam_Side", "left": "Cam_Left",
               "materials": "Cam_Studio_Materials", "cockpit": "Cam_Studio_Cockpit"}
    previous = (scene.camera, scene.render.resolution_percentage, scene.cycles.samples, scene.render.filepath)
    if preview:
        scene.render.resolution_percentage = 60
        scene.cycles.samples = 40
    try:
        for tag in views:
            scene.camera = bpy.data.objects[cameras[tag]]
            suffix = "_preview" if preview else ""
            scene.render.filepath = os.path.join(out, f"render_{size}_studio_{tag}{suffix}.png")
            bpy.ops.render.render(write_still=True)
            print(f"[studio] Rendered {scene.render.filepath}")
    finally:
        scene.camera, scene.render.resolution_percentage, scene.cycles.samples, scene.render.filepath = previous


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", choices=["2XS", "XS", "S", "M", "L", "XL", "2XL"])
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--render-only", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--samples", type=int, default=160)
    parser.add_argument("--views", nargs="+", default=["34", "side", "materials", "cockpit"],
                        choices=["34", "side", "left", "materials", "cockpit"])
    args = parser.parse_args(args)
    scene = bpy.context.scene
    root = next(ob for ob in scene.objects if ob.type == "EMPTY" and ob.name.startswith("Endurace_CF"))
    model_size = root.get("frameSize", root.name.rsplit("_", 1)[-1])
    if args.size is not None and args.size != model_size:
        parser.error(f"Loaded geometry is size {model_size}; rebuild with build_endurace.py -- --size {args.size} first.")
    args.size = model_size
    if not args.render_only:
        configure_studio(scene, OUT, args.size, args.samples)
        path = os.path.join(OUT, f"endurace_cf_slx_7_axs_{args.size}_studio.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path)
        print(f"[studio] Saved {path}")
    else:
        configure_gpu(scene)
    if args.render or args.render_only:
        render_views(scene, OUT, args.size, args.preview, tuple(args.views))


if __name__ == "__main__":
    main()
