# -*- coding: utf-8 -*-
"""Six views of each clip, rendered off the model, for the shop that has to fold them.

    blender -b -P data/clips9_render.py     ->  site/renders/clip_<code>_<view>.png
    python data/clips9_sheet.py             ->  drawings/R1..R4_<code>_CN_EN.png / .svg

dxf/06 and S8 give a fabricator the flat blank, the section and the fold lines, which is what he
needs to CUT and BEND.  What neither shows is the part in the hand: which way the lip actually
hooks, what the fold looks like from underneath, and that the two lips face each other rather
than standing apart.  That has been the one thing misread about this clip from the beginning, and
a picture of the solid settles it in a way an orthographic section does not.

The geometry, the metal and the light rig are imported from build_blender9, not rewritten, so
these renders are the same part the client already has in the GLB and the .blend.  Cameras are
ORTHOGRAPHIC on all six: a fabricator scales off what he is looking at, and a perspective view of
a 68 mm section is a drawing of a part nobody made.
"""
import bpy, bmesh, json, math, os, sys
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_blender9 as B          # geometry, materials, lights; its own build is guarded

ROOT = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(ROOT, 'site', 'renders')
os.makedirs(OUT, exist_ok=True)
S = B.S
CL = json.load(open(os.path.join(HERE, 'clips9.json'), encoding='utf-8'))['clips']
PROF = B.PROF
HOLE_R = 1.75*S

# How much of a long clip is drawn.  LC-1366 is twenty times as long as it is wide; a view of the
# whole thing shows a line.  Its END is what a fabricator sets up: the margin to the first hole,
# the return of the lip, the cut face.  The sheet says the full length in its title block.
LONG_CUT = 320.0

# tag, camera direction (from the part towards the camera), up hint, caption
VIEWS = (
    ('iso_a',  Vector((-0.62, -0.72, 0.68)), Vector((0, 0, 1)),
     ('立体图 A：上方前侧', 'ISOMETRIC A - from above and in front')),
    # not (0.66, 0.70, ...): that azimuth runs straight down the 45 deg hypotenuse of both
    # pockets, and the part came out as a sliver
    ('iso_b',  Vector((0.80, -0.36, 0.58)), Vector((0, 0, 1)),
     ('立体图 B：上方右侧', 'ISOMETRIC B - from above and to the right')),
    ('under',  Vector((-0.50, 0.58, -0.80)), Vector((0, 0, -1)),
     ('立体图 C：仰视，看背面与孔', 'ISOMETRIC C - underside, the back face and the holes')),
    ('plan',   Vector((0.0, 0.0, 1.0)), Vector((0, 1, 0)),
     ('俯视 1:1', 'PLAN, looking down')),
    ('end',    Vector((-1.0, 0.0, 0.0)), Vector((0, 0, 1)),
     ('端视：这是折弯的样子', 'END VIEW - this is the fold')),
    ('side',   Vector((0.0, -1.0, 0.0)), Vector((0, 0, 1)),
     ('侧视', 'SIDE VIEW')),
)


def clip_object(c):
    """one clip, alone, on its own at the origin, with its fixing holes cut through

    Outline and holes come from boards.json's clipgeo, which is what dxf/06, sheet S8 and the
    website all draw from - clips9.json carries no hole list for a pocket, and reading it there
    left both pockets rendered as blank plates with the one thing that gets drilled missing.
    """
    g = B.CLIPGEO[c['code']]
    holes = [tuple(q) for q in g['holes']]
    bm = bmesh.new()
    if c['kind'] == 'RAIL':
        L = min(c['length'], LONG_CUT)
        quad = [(0.0, 0.0), (L, 0.0), (L, PROF['flat']), (0.0, PROF['flat'])]
        B.clip_rail(bm, quad, PROF)
        holes = [q for q in holes if q[0] <= L+1e-6]
    else:
        base = [tuple(q) for q in g['base']]
        B.clip_pocket(bm, base, g['lipped'], PROF, g.get('tabs'), g.get('tab_w'))
    me = bpy.data.meshes.new('clip'); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(c['code'], me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(B.metal('steel', B.hexv('#b9bec4'), rough=0.34))

    # the holes are cut, not drawn on: on a 0.25 sheet a fabricator wants to see daylight through
    # them, and a disc printed on the face reads as a mark to be punched later
    if holes:
        cyl = bmesh.new()
        for hx, hy in holes:
            bmesh.ops.create_cone(cyl, cap_ends=True, segments=32,
                                  radius1=HOLE_R, radius2=HOLE_R, depth=40*S,
                                  matrix=__import__('mathutils').Matrix.Translation(
                                      (hx*S, hy*S, 0.0)))
        cme = bpy.data.meshes.new('cut'); cyl.to_mesh(cme); cyl.free()
        cob = bpy.data.objects.new('cut', cme)
        bpy.context.scene.collection.objects.link(cob)
        m = ob.modifiers.new('holes', 'BOOLEAN')
        m.operation, m.object, m.solver = 'DIFFERENCE', cob, 'EXACT'
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier=m.name)
        bpy.data.objects.remove(cob, do_unlink=True)
    return ob


def shot(ob, dirv, up, path, res=1500, pad=1.14):
    """an ORTHOGRAPHIC view along dirv, framed on the object"""
    for o in list(bpy.context.scene.objects):
        if o.type == 'CAMERA':
            bpy.data.objects.remove(o, do_unlink=True)
    cam = bpy.data.cameras.new('C'); cam.type = 'ORTHO'
    co = bpy.data.objects.new('C', cam)
    bpy.context.scene.collection.objects.link(co)
    bpy.context.scene.camera = co

    d = dirv.normalized()
    bb = [ob.matrix_world @ Vector(v) for v in ob.bound_box]
    cen = sum(bb, Vector()) / 8.0
    # the frame is the part measured ACROSS the view, so the scale is honest whatever the angle
    r = d.cross(up if abs(d.dot(up)) < 0.99 else Vector((0, 1, 0))).normalized()
    u2 = r.cross(d).normalized()
    w = max(abs((p-cen).dot(r)) for p in bb)*2
    h = max(abs((p-cen).dot(u2)) for p in bb)*2
    cam.ortho_scale = max(w, h*1.0)*pad
    co.location = cen + d*max(w, h)*4.0
    co.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    if abs(d.dot(Vector((0, 0, 1)))) < 0.999:
        co.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()

    sc = bpy.context.scene
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.film_transparent = True
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    for c in CL:
        B.wipe()
        B.world()
        B.add_lights()
        B.setup_render((1500, 1500), samples=256)
        ob = clip_object(c)
        n = 0
        for tag, dirv, up, _cap in VIEWS:
            p = os.path.join(OUT, 'clip_%s_%s.png' % (c['code'], tag))
            shot(ob, dirv, up, p)
            n += 1
        print('%-10s %-7s %6d tris   %d views'
              % (c['code'], c['kind'], len(ob.data.polygons), n))
    print('ALL DONE')
