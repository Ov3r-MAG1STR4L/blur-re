"""Méthode C : simplification quadrique de MeshLab qui garde les UV (textures d'origine, pas de cuisson),
préserve les bords (passages de roue, contours des vitres) et évite de retourner les normales.
python method_C_meshlab.py entree.obj sortie.obj triangles"""
import sys

import pymeshlab

src, out, target = sys.argv[1], sys.argv[2], int(sys.argv[3])
ms = pymeshlab.MeshSet()
ms.load_new_mesh(src)
print('avant', ms.current_mesh().face_number())
# soudure des sommets coupés aux coutures d'UV (les UV restent par coin de face) + faces en double
ms.meshing_merge_close_vertices(threshold=pymeshlab.PureValue(0.0002))
ms.meshing_remove_duplicate_faces()
ms.meshing_remove_null_faces()
ms.meshing_decimation_quadric_edge_collapse_with_texture(
    targetfacenum=target, qualitythr=0.3, extratcoordw=1.0, preserveboundary=True, boundaryweight=2.0,
    optimalplacement=True, preservenormal=True, planarquadric=True)
print('après', ms.current_mesh().face_number())
ms.save_current_mesh(out, save_textures=True)
