"""Export the actual Blender bike as an articulated, self-contained web GLB.

Blender --background endurace_cf_slx_7_axs_S.blend --python-exit-code 1 --python export_viewer.py
Export happens in memory; it never writes over the source .blend.
"""
import hashlib
import json
import math
import os
import re
import shutil
import wave

import bpy
import numpy as np
from mathutils import Matrix, Vector

OUT = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(OUT, "public", "models")
TEXTURE_DIR = os.path.join(MODEL_DIR, "textures")
os.makedirs(TEXTURE_DIR, exist_ok=True)


def image(name, rgb, colour_space="sRGB"):
    h, w, _ = rgb.shape
    rgba = np.concatenate((rgb, np.ones((h, w, 1))), axis=2).astype(np.float32)
    im = bpy.data.images.new(name, width=w, height=h)
    im.colorspace_settings.name = colour_space
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = os.path.join(TEXTURE_DIR, name + ".png")
    im.file_format = "PNG"
    im.save()
    im.pack()
    return im


def web_materials():
    # glTF cannot serialize Blender procedural shader graphs. Supply explicit PBR maps.
    n = 1024
    y, x = np.mgrid[0:n, 0:n] / n * 4
    over = ((np.floor(x) - np.floor(y)) % 4 < 2)
    bundle = np.where(over, np.sin((x % 1) * math.pi), np.sin((y % 1) * math.pi))
    strands = np.where(over, np.sin(x * math.tau * 48), np.sin(y * math.tau * 48))
    height = bundle * 0.8 + strands * 0.035
    brightness = 0.065 + 0.070 * bundle
    base = image("carbon_3k_base", np.stack((brightness * 0.94, brightness, brightness * 1.07), axis=-1))
    rough = image("carbon_3k_roughness", np.repeat((0.29 + 0.035 * (1 - bundle))[..., None], 3, axis=-1), "Non-Color")
    dy, dx = np.gradient(height)
    normals = np.stack((-dx * 2.5, -dy * 2.5, np.ones_like(dx)), axis=-1)
    normals /= np.linalg.norm(normals, axis=-1, keepdims=True)
    normal = image("carbon_3k_normal", normals * 0.5 + 0.5, "Non-Color")
    carbon = bpy.data.materials.get("Carbon Weave")
    if carbon:
        nt = carbon.node_tree
        nt.nodes.clear()
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        b.inputs["Roughness"].default_value = 0.30
        b.inputs["Coat Weight"].default_value = 1
        b.inputs["Coat Roughness"].default_value = 0.10
        b.inputs["Anisotropic"].default_value = 0.55
        b.inputs["Anisotropic Rotation"].default_value = 0.125
        uv = nt.nodes.new("ShaderNodeUVMap")
        uv.uv_map = "CarbonMetricUV"
        mapping = nt.nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (100, 100, 100)
        mapping.inputs["Rotation"].default_value.z = math.radians(45)
        nt.links.new(uv.outputs[0], mapping.inputs[0])
        for im, socket in ((base, "Base Color"), (rough, "Roughness"), (normal, "Normal")):
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = im
            nt.links.new(mapping.outputs[0], tex.inputs["Vector"])
            if socket == "Normal":
                nm = nt.nodes.new("ShaderNodeNormalMap")
                nm.uv_map = "CarbonMetricUV"
                nt.links.new(tex.outputs[0], nm.inputs["Color"])
                nt.links.new(nm.outputs[0], b.inputs[socket])
            else:
                nt.links.new(tex.outputs[0], b.inputs[socket])
        output = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(b.outputs[0], output.inputs[0])

    rng = np.random.default_rng(44)
    grain = rng.normal(0, 0.09, (256, 256, 2))
    z = np.ones((256, 256, 1))
    normal_grain = np.concatenate((grain, z), axis=-1)
    normal_grain /= np.linalg.norm(normal_grain, axis=-1, keepdims=True)
    rubber_normal = image("rubber_micro_normal", normal_grain * 0.5 + 0.5, "Non-Color")
    roughness = {"Crystal White": 0.24, "Tire Rubber": 0.65, "Hood Rubber": 0.66,
                 "Bar Tape": 0.64, "Saddle Microfibre": 0.53, "Saddle Side Panel": 0.62,
                 "Pedal Resin": 0.43, "FD Arm Matte": 0.7, "Steel": 0.27,
                 "Rotor Steel": 0.32, "Cassette Steel": 0.23, "Chain Steel": 0.28,
                 "Pedal Plate": 0.30, "AXS Silver Grey": 0.34, "FD Cage Polished": 0.19,
                 "Dark Metal": 0.30, "DT Swiss Hub Black": 0.29, "Chainring Black": 0.31}
    rubber = {"Tire Rubber", "Hood Rubber", "Bar Tape", "Saddle Microfibre", "Saddle Side Panel", "Pedal Resin"}
    for name, roughness_value in roughness.items():
        mat = bpy.data.materials.get(name)
        if not mat:
            continue
        nt = mat.node_tree
        old = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        values = {s.name: tuple(s.default_value) if hasattr(s.default_value, "__len__") else s.default_value
                  for s in old.inputs if s.name in ("Base Color", "Metallic", "IOR", "Coat Weight", "Coat Roughness", "Anisotropic")}
        nt.nodes.clear()
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        for name_, value in values.items():
            b.inputs[name_].default_value = value
        b.inputs["Roughness"].default_value = roughness_value
        if name in rubber:
            tc = nt.nodes.new("ShaderNodeTexCoord")
            mapping = nt.nodes.new("ShaderNodeMapping")
            mapping.inputs["Scale"].default_value = (35, 18, 1)
            nt.links.new(tc.outputs["UV"], mapping.inputs[0])
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = rubber_normal
            nt.links.new(mapping.outputs[0], tex.inputs[0])
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nm.inputs["Strength"].default_value = 0.45
            nt.links.new(tex.outputs[0], nm.inputs["Color"])
            nt.links.new(nm.outputs[0], b.inputs["Normal"])
        output = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(b.outputs[0], output.inputs[0])


# ---------------------------------------------------------------------------------------------------
# Procedural rubber details -> tileable textures.
# build_endurace.py gives Bar Tape, Tire Rubber and Hood Rubber procedural bump patterns that glTF
# cannot store (and web_materials() would replace with a generic grain). Each pattern below is the
# SAME formula as its Blender shader, sampled over one repeating tile in real millimetres, so the
# normals match the procedural bump depth. Tiles wrap seamlessly (np.roll derivatives).

def srgb(linear):
    linear = np.clip(linear, 0, 1)
    return np.where(linear <= 0.0031308, linear * 12.92, 1.055 * np.power(linear, 1 / 2.4) - 0.055)


def normal_from_height(height_mm, du_mm, dv_mm, wrap_v=True):
    """Tangent-space normal map (OpenGL / glTF convention: +X = +U, +Y = +V) from a height field
    whose rows are V (bottom row first, as Blender stores pixels) and columns are U."""
    ddu = (np.roll(height_mm, -1, axis=1) - np.roll(height_mm, 1, axis=1)) / (2 * du_mm)
    if wrap_v:
        ddv = (np.roll(height_mm, -1, axis=0) - np.roll(height_mm, 1, axis=0)) / (2 * dv_mm)
    else:
        ddv = np.gradient(height_mm, dv_mm, axis=0)
    n = np.stack((-ddu, -ddv, np.ones_like(ddu)), axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def rebuild_material(mat, *, base, roughness, normal_img, uv_map, scale_u=1.0, scale_v=1.0,
                     normal_strength=1.0, base_img=None):
    nt = mat.node_tree
    nt.nodes.clear()
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = base
    b.inputs["Roughness"].default_value = roughness
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = uv_map
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (scale_u, scale_v, 1)
    nt.links.new(uv.outputs[0], mapping.inputs[0])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = normal_img
    nt.links.new(mapping.outputs[0], tex.inputs["Vector"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.uv_map = uv_map
    nm.inputs["Strength"].default_value = normal_strength
    nt.links.new(tex.outputs[0], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], b.inputs["Normal"])
    if base_img is not None:
        btex = nt.nodes.new("ShaderNodeTexImage")
        btex.image = base_img
        nt.links.new(mapping.outputs[0], btex.inputs["Vector"])
        nt.links.new(btex.outputs[0], b.inputs["Base Color"])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(b.outputs[0], out.inputs[0])


def tape_wrap_textures(size_u=256, size_v=1024):
    """Bar Tape: h = fract(4u + v) ** 6 (Bump 1.0, 0.8 mm); colour ramp 0.007 -> 0.020 on fract.
    Tile = one 25 mm wrap (u in [0, 0.25) of the 100 mm/unit sweep UV) x the full bar circumference."""
    v_, u_ = np.mgrid[0:size_v, 0:size_u]
    phase = (u_ / size_u + v_ / size_v) % 1.0
    rng = np.random.default_rng(7)
    height = 0.8 * phase ** 6 + rng.normal(0, 0.004, phase.shape)        # + fine rubber grain
    circumference = math.pi * 26.0                                       # ~26 mm taped bar
    normal = image("bar_tape_wrap_normal", normal_from_height(height, 25.0 / size_u, circumference / size_v),
                   "Non-Color")
    shade = srgb(0.007 + 0.013 * phase)
    base = image("bar_tape_wrap_base", np.repeat(shade[..., None], 3, axis=-1))
    return normal, base


TREAD_R, TREAD_r = 0.327, 0.016            # Pro One 32 mm torus: major / minor radius (m)
TREAD_CYCLES = 860                         # sin(theta * 860 ...): 860 tread cycles per revolution


def tread_texture(size_u=32, size_v=2048):
    """Tire Rubber shoulders: wave = sin(theta*860 + |z|*2500), masked to |z| in (3.5, 12) mm and
    r > 336 mm (slick centre). Tile = one tread cycle (u) x the full minor circle phi (v)."""
    v_, u_ = np.mgrid[0:size_v, 0:size_u]
    phi = (v_ / size_v) * 2 * math.pi - math.pi
    z = np.abs(TREAD_r * np.sin(phi))
    r = TREAD_R + TREAD_r * np.cos(phi)
    mask = (z > 0.0035) & (z < 0.012) & (r > 0.336)
    wave = np.sin(2 * math.pi * u_ / size_u + z * 2500)
    height = 0.2 * 0.35 * wave * mask                                     # mm (Bump 0.35 x 0.2 mm)
    du = 2 * math.pi * (TREAD_R + TREAD_r) * 1000 / TREAD_CYCLES / size_u
    dv = 2 * math.pi * TREAD_r * 1000 / size_v
    return image("tire_tread_normal", normal_from_height(height, du, dv), "Non-Color")


GRIP_PERIOD_MM = 2 * math.pi               # sin(x*1000 ...) with x in m: 6.28 mm period
GRIP_Y_MM = 50.0                           # tile covers +-50 mm of arc around the hood (top centre = 0)


def grip_texture(size_u=64, size_v=512):
    """Hood Rubber: chev = sin(x*1000 + |y|*1000), dash = sin(y*700), h = max(chev-0.6,0)*max(dash,0)
    (Bump 0.6 x 0.8 mm). Tile = one chevron period in x (u) x arc position around the hood (v);
    on the top surface arc ~= y, so the top matches the procedural exactly."""
    v_, u_ = np.mgrid[0:size_v, 0:size_u]
    y_mm = (v_ / size_v) * 2 * GRIP_Y_MM - GRIP_Y_MM
    chev = np.sin(2 * math.pi * u_ / size_u + np.abs(y_mm))
    dash = np.sin(0.7 * y_mm)
    rng = np.random.default_rng(11)
    height = 0.8 * 0.6 * np.maximum(chev - 0.6, 0) * np.maximum(dash, 0) + rng.normal(0, 0.003, chev.shape)
    return image("hood_grip_normal", normal_from_height(height, GRIP_PERIOD_MM / size_u, 2 * GRIP_Y_MM / size_v,
                                                       wrap_v=False), "Non-Color")


def add_uv_layer(ob, name, fn, wrap_u=False, wrap_v=False):
    """New UV layer from local vertex positions (m). fn(co) -> (u, v). wrap_u / wrap_v fix faces that
    cross the 0/1 seam of an angular coordinate."""
    me = ob.data
    layer = me.uv_layers.get(name) or me.uv_layers.new(name=name)
    for poly in me.polygons:
        uvs = [fn(me.vertices[me.loops[li].vertex_index].co) for li in poly.loop_indices]
        if wrap_u and max(u for u, _ in uvs) - min(u for u, _ in uvs) > 0.5:
            uvs = [(u + 1.0 if u < 0.5 else u, v) for u, v in uvs]
        if wrap_v and max(v for _, v in uvs) - min(v for _, v in uvs) > 0.5:
            uvs = [(u, v + 1.0 if v < 0.5 else v) for u, v in uvs]
        for li, uv in zip(poly.loop_indices, uvs):
            layer.data[li].uv = uv
    return layer


def rubber_pattern_materials(scene):
    """Replace the generic grain on Bar Tape / Tire Rubber / Hood Rubber with their real patterns."""
    tape = bpy.data.materials.get("Bar Tape")
    if tape:
        normal, base = tape_wrap_textures()
        rebuild_material(tape, base=(0.012, 0.012, 0.012, 1), roughness=0.64, normal_img=normal, uv_map="UVMap",
                         scale_u=4.0, normal_strength=1.0, base_img=base)
    tire = bpy.data.materials.get("Tire Rubber")
    if tire:
        def tread_uv(co):
            theta = math.atan2(co.y, co.x) % (2 * math.pi)
            phi = math.atan2(co.z, math.hypot(co.x, co.y) - TREAD_R)
            return theta / (2 * math.pi), (phi + math.pi) / (2 * math.pi)
        for ob in scene.objects:
            if ob.type == "MESH" and ob.name.endswith("_wheel_tire"):
                add_uv_layer(ob, "TreadUV", tread_uv, wrap_u=True, wrap_v=True)
        rebuild_material(tire, base=(0.015, 0.015, 0.015, 1), roughness=0.65, normal_img=tread_texture(),
                         uv_map="TreadUV", scale_u=TREAD_CYCLES, normal_strength=1.0)
    hood = bpy.data.materials.get("Hood Rubber")
    if hood:
        for ob in scene.objects:
            if not (ob.type == "MESH" and ob.name.startswith("hood_")):
                continue
            # Unwrap around each lofted section (rings share x): v = arc length from the top centre,
            # so the chevrons stay undistorted down the steep hood sides (a top-down projection
            # would stretch them there).
            rings = {}
            for vert in ob.data.vertices:
                rings.setdefault(round(vert.co.x, 4), []).append(vert.co)
            centre = {k: sum((c.z for c in cs), 0.0) / len(cs) for k, cs in rings.items()}
            radius = {k: sum(math.hypot(c.y, c.z - centre[k]) for c in cs) / len(cs) for k, cs in rings.items()}
            def grip_uv(co, centre=centre, radius=radius):
                k = round(co.x, 4)
                psi = math.atan2(co.y, co.z - centre[k])               # 0 at the top, +-pi underneath
                arc_mm = psi * radius[k] * 1000
                return co.x * 1000 / GRIP_PERIOD_MM, (arc_mm + GRIP_Y_MM) / (2 * GRIP_Y_MM)
            add_uv_layer(ob, "GripUV", grip_uv, wrap_v=True)
        rebuild_material(hood, base=(0.015, 0.015, 0.016, 1), roughness=0.66, normal_img=grip_texture(),
                         uv_map="GripUV", normal_strength=1.0)


def group(name, parent, location=(0, 0, 0)):
    ob = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    ob.location = location
    ob.empty_display_type = "PLAIN_AXES"
    ob["part"] = name
    return ob


def move(ob, parent):
    world = ob.matrix_world.copy()
    ob.parent = parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_world = world


def refresh_model_url(dest):
    """Refresh the viewer's cache key after exporting, including during local development."""
    with open(dest, "rb") as handle:
        version = hashlib.sha256(handle.read()).hexdigest()[:12]
    path = os.path.join(OUT, "src", "lib", "parts.ts")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    url = f"/models/endurace.glb?v={version}"
    updated, count = re.subn(r'(export const MODEL_URL = ")[^"]*(";)',
                             lambda match: match[1] + url + match[2], source)
    if count != 1:
        raise ValueError("Expected exactly one MODEL_URL declaration in src/lib/parts.ts")
    if updated != source:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(updated)
    print(f"[viewer] Model URL: {url}")


def main():
    scene = bpy.context.scene
    root = next(ob for ob in scene.objects if ob.type == "EMPTY" and ob.name.startswith("Endurace_CF"))
    frame_size = root.get("frameSize", root.name.rsplit("_", 1)[-1])
    root["frameSize"] = frame_size
    originals = [ob for ob in scene.objects if ob.type in ("MESH", "CURVE") and ob.parent == root]
    # Curves such as spokes, hoses, rails, and hub shells must be preserved as evaluated meshes.
    bpy.ops.object.select_all(action="DESELECT")
    for ob in originals:
        ob.select_set(ob.type == "CURVE")
    bpy.context.view_layer.objects.active = next(ob for ob in originals if ob.type == "CURVE")
    bpy.ops.object.convert(target="MESH")
    bpy.context.view_layer.update()
    originals = [ob for ob in scene.objects if ob.type == "MESH" and ob.parent == root]
    if not scene.get("studio_materials_version"):
        import sys
        sys.path.insert(0, OUT)
        from upgrade_studio import upgrade_materials
        upgrade_materials(scene)
    web_materials()
    rubber_pattern_materials(scene)

    front = scene.objects["front_wheel_tire"].matrix_world.translation.copy()
    rear = scene.objects["rear_wheel_tire"].matrix_world.translation.copy()
    frame = group("Frame", root)
    name_sticker = group("NameSticker", frame)
    name_sticker["brand"] = "VeloInk"
    name_sticker["source"] = "https://veloink.com/"
    fw, rw = group("FrontWheel", root, front), group("RearWheel", root, rear)
    front_decals, rear_decals = group("FrontEnveDecals", fw), group("RearEnveDecals", rw)
    for decals in (front_decals, rear_decals):
        decals["upgrade"] = "EnveDecals"
        decals["brand"] = "ENVE"
        decals["finish"] = "white"
    fh, rh = group("FrontHub", fw), group("RearHub", rw)
    crank = group("Crank", root)
    pedals = group("Pedals", crank)
    power_meter = group("PowerMeter", crank)
    fd, rd = group("FrontDerailleur", root), group("RearDerailleur", root)
    light = group("RearLight", root)
    cockpit, saddle = group("Cockpit", root), group("Saddle", root)
    stem, computer = group("Stem", cockpit), group("BikeComputer", cockpit)
    computer_mount = group("ComputerMount", cockpit)
    rh["ratchetTeeth"] = 54
    rh["originalRatchetTeeth"] = 36
    cages, brakes, drivetrain = group("BottleCages", root), group("Brakes", root), group("Drivetrain", root)
    for wheel in (fw, rw):
        # Blender +Y axle becomes glTF -Z. Direction sign is immaterial for a full rotation.
        wheel["wheelAxis"] = [0.0, 0.0, 1.0]
        wheel["pivotAtAxle"] = True
    bpy.context.view_layer.update()
    for ob in originals:
        name = ob.name
        parent = frame
        if name.startswith(("front_wheel_", "rear_wheel_")):
            is_front = name.startswith("front_wheel_")
            wheel, hub = (fw, fh) if is_front else (rw, rh)
            if "_enve_" in name:
                parent = front_decals if is_front else rear_decals
            else:
                parent = frame if "_axle" in name else hub if "_hub" in name else wheel
        elif name.startswith("nametag_"):
            parent = name_sticker
        elif name.startswith("pedal_"):
            parent = pedals
        elif name.startswith(("crank_spindle", "quarq")):
            parent = power_meter
        elif name.startswith(("crank_", "chainring", "ring_", "quarq")):
            parent = crank
        elif name.startswith("fd_"):
            parent = fd
        elif name.startswith("rd_"):
            parent = rd
        elif name.startswith("flash_"):
            parent = light
        elif name.startswith("stem"):
            parent = stem
        elif name.startswith(("gear_groove", "computer_mount")):
            parent = computer_mount
        elif name.startswith(("bryton", "computer")):
            parent = computer
        elif name.startswith(("steerer", "handlebar", "bar_", "hood_", "lever_", "paddle_", "shifter_")):
            parent = cockpit
        elif name.startswith(("saddle", "seatpost")):
            parent = saddle
        elif name.startswith("cage_"):
            parent = cages
        elif name.startswith(("front_caliper", "rear_caliper")):
            parent = brakes
        elif name.startswith(("cassette", "chain", "cog_")):
            parent = drivetrain
        move(ob, parent)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    for ob in root.children_recursive:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = root
    dest = os.path.join(MODEL_DIR, "endurace.glb")
    bpy.ops.export_scene.gltf(filepath=dest, export_format="GLB", use_selection=True,
        export_apply=True, export_yup=True, export_extras=True,
        export_cameras=False, export_lights=False, export_animations=False,
        export_image_format="AUTO", export_materials="EXPORT")
    manifest = {"file": "/models/endurace.glb", "source": os.path.basename(bpy.data.filepath),
                "frameSize": frame_size, "meshObjects": len(originals), "units": "metres", "upAxis": "+Y",
                "wheelAxle": "+Z", "parts": [ob.name for ob in (frame, fw, rw, fh, rh, crank, pedals, power_meter, fd, rd, light, cockpit, stem, computer, computer_mount, saddle, cages, brakes, drivetrain, name_sticker, front_decals, rear_decals)],
                "notes": ["FrontLight is not present on the owner's Blender model.",
                          "Cassette, chain, through axles and brake calipers remain stationary while wheels coast.",
                          "Blender procedural finishes are converted to web PBR maps; all original mesh detail and decals are preserved."]}
    with open(os.path.join(MODEL_DIR, "manifest.json"), "w") as handle:
        json.dump(manifest, handle, indent=2)
    env_dir = os.path.join(OUT, "public", "environment")
    os.makedirs(env_dir, exist_ok=True)
    shutil.copyfile(os.path.join(OUT, "studio_small_09_2k.hdr"), os.path.join(env_dir, "studio.hdr"))
    make_audio()
    refresh_model_url(dest)
    print(f"[viewer] Exported {len(originals)} mesh objects; {os.path.getsize(dest) / 1e6:.1f} MB -> {dest}")


def make_audio():
    """Supply a demo only when no owner recording exists; never overwrite custom audio."""
    audio_dir = os.path.join(OUT, "public", "audio")
    os.makedirs(audio_dir, exist_ok=True)
    if os.path.exists(os.path.join(audio_dir, "freehub.wav")):
        print("[viewer] Preserving existing freehub audio.")
        return
    sample_rate = 44100
    t = np.arange(sample_rate * 2) / sample_rate
    # Owner's 54T upgrade at 180 rpm: 162 ticks per second, seamless two-second demo.
    phase = (t * 162) % 1
    rng = np.random.default_rng(350)
    noise = rng.standard_normal(len(t))
    noise -= np.roll(noise, 1) * 0.85
    pulse = np.exp(-phase * 24)
    signal = pulse * (noise * 0.20 + np.sin(phase * 150) * 0.18 + np.sin(phase * 290) * 0.08)
    signal = np.clip(signal * 0.6, -1, 1)
    with wave.open(os.path.join(audio_dir, "freehub.wav"), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes((signal * 32767).astype("<i2").tobytes())
    with open(os.path.join(audio_dir, "LICENSE.txt"), "w") as handle:
        handle.write("freehub.wav is an original synthetic freehub ratchet sound generated by export_viewer.py.\nReleased under CC0 1.0. It is a demonstration, not a recording of a DT Swiss hub.\nhttps://creativecommons.org/publicdomain/zero/1.0/\n")


if __name__ == "__main__":
    main()
