from qgis.PyQt.QtWidgets import QAction, QMenu, QMessageBox, QInputDialog,QDockWidget, QWidget, QVBoxLayout, QTextEdit
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsWkbTypes, QgsCoordinateTransform,
    QgsCoordinateReferenceSystem, QgsGeometry, QgsPointXY, QgsSpatialIndex,QgsRectangle,QgsDistanceArea
)
from collections import defaultdict, Counter
import os
import unicodedata
 
class MonPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.menu = None
        self.action_main = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        self.menu = QMenu("🔧 Outils Vecteurs", self.iface.mainWindow())


        actions = [
            ("✔ NULL VALUES", self.null_values),
            ("✔ Doublons NOM et ID", self.check_name_duplicates),
            ("✔ Doublons Géométriques", self.check_geometry_duplicates),
            ("✔ ACCROCHAGE", self.accrochage_lignes_points),
            ("✔ GEOMETRY FANTOME", self.detecter_fantomes),
            ("✔ Superposition CANAL/TRANC", self.verifier_tranchee_canalisation),
            ("✔ TYPE CANAL", self.verifier_type_canal),
            ("✔ TYPE SUPPORT", self.verifier_supports),
            ("✔ TYPE CHAM-CANAL", self.verifier_connexions),
            ("✔ CPS TRANC-CANAL", self.verifier_cps_tranchee),
            ("✔ FONCTION CHAMBRE",self.verifier_fonction_chambre),
            #("✔ Vérif PC superposition", self.verifier_pc_superposition),
            
        ]
        for label, func in actions:
            action = QAction(label, self.iface.mainWindow())
            action.triggered.connect(func)
            self.menu.addAction(action)

        self.action_main = QAction(QIcon(icon_path), "VERIF'INFRA", self.iface.mainWindow())
        self.action_main.setMenu(self.menu)

        self.iface.addPluginToMenu("🔎 Vérification Réseau Infra", self.menu.menuAction())
        self.iface.addToolBarIcon(self.action_main)

    def unload(self):
        self.iface.removePluginMenu("▶ Outils Vecteurs", self.action_main)
        self.iface.removeToolBarIcon(self.action_main)

    def get_layer_by_name(self, name):
        project = QgsProject.instance()
        layers = project.mapLayersByName(name)
        return layers[0] if layers else None
    
    
    """
    fonction 1: doublons géométriques
    fonction 2: doublons de noms et id
    fonction 3: NULL values
    fonction 4: Geometry fantome
    fonction 5: Accrochage
    fonction 6: Superposiion tranchee canalisation
    fonction 7: TYPE CANAL
    fonction 8: TYPE Support
    fonction 9: chambre Canal
    fonction 10: CPS canal tranch
    fonction 11: Fonction chambre
    fonction 12:

    """

#============================================================
# ============================================================
# ============================================================
# ============================================================
# ===============     Fonction 1 :#DOUBLONS GEOMETRIQUES    ==============================
#  ============================================================
# ============================================================
# ============================================================
# ============================================================
# ============================================================
    

    def check_geometry_duplicates(self):
        project = QgsProject.instance()
        infra_group = project.layerTreeRoot().findGroup("Infrastructure")
        if infra_group is None:
            QMessageBox.information(None, "Doublons", "Groupe Infrastructure introuvable.")
            return

        all_layers = [node.layer() for node in infra_group.findLayers() if isinstance(node.layer(), QgsVectorLayer)]

        exceptions_par_paires = {
            ("Canalisation", "Tranchee"),
            ("Batiment", "Point Technique"),
            # ajouter d'autres paires ici si besoin
        }

        layer_points = {}
        for layer in all_layers:
            if QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.PointGeometry:
                continue
            src = layer.crs()
            # Pas de transformation, on reste en 4326 mais on utilisera QgsDistanceArea pour distances géodésiques
            coords_dict = defaultdict(list)
            for f in layer.getFeatures():
                g = f.geometry()
                if not g or g.isEmpty():
                    continue
                geom = QgsGeometry(g)
                pt = geom.asPoint()
                key = (round(pt.x(), 5), round(pt.y(), 5))
                fields_names = [fld.name() for fld in layer.fields()]
                label = f["NOM"] if ("NOM" in fields_names and f["NOM"]) else f"ID {f.id()}"
                coords_dict[key].append((f.id(), label, pt, f))
            layer_points[layer] = coords_dict

        msg = ""
        doubl_ids_per_layer = defaultdict(set)

        # Détection doublons exacts
        for layer, coords_dict in layer_points.items():
            layer.removeSelection()
            for key, feats in coords_dict.items():
                if len(feats) > 1:
                    ids = [fid for fid, _, _, _ in feats]
                    noms = [label for _, label, _, _ in feats]
                    doubl_ids_per_layer[layer].update(ids)
                    layer.selectByIds(ids)
                    msg += f"\n🟢 Doublons exacts {layer.name()}: {', '.join(noms)}"

        # Détection superpositions interdites entre couches différentes
        checked_pairs = set()
        for layer1 in layer_points:
            for layer2 in layer_points:
                if layer1 == layer2:
                    continue
                pair = (layer1.name(), layer2.name())
                pair_inv = (layer2.name(), layer1.name())
                if pair in checked_pairs or pair_inv in checked_pairs:
                    continue
                checked_pairs.add(pair)
                checked_pairs.add(pair_inv)

                if pair in exceptions_par_paires or pair_inv in exceptions_par_paires:
                    continue

                cds1 = layer_points[layer1]
                cds2 = layer_points[layer2]

                selected_fids_1 = set(layer1.selectedFeatureIds())
                selected_fids_2 = set(layer2.selectedFeatureIds())

                for key in cds1:
                    if key in cds2:
                        for id1, nom1, _, _ in cds1[key]:
                            if id1 in doubl_ids_per_layer[layer1]:
                                continue
                            for id2, nom2, _, _ in cds2[key]:
                                if id2 in doubl_ids_per_layer[layer2]:
                                    continue
                                selected_fids_1.add(id1)
                                selected_fids_2.add(id2)
                                msg += f"\n🔴 Superposition entre '{nom1}' ({layer1.name()}) et '{nom2}' ({layer2.name()})"

                layer1.selectByIds(list(selected_fids_1))
                layer2.selectByIds(list(selected_fids_2))

        # Détection des doublons de LIGNES
        for layer in all_layers:
            if QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.LineGeometry:
                continue

            feats = list(layer.getFeatures())
            if len(feats) < 2:
                continue

            spatial_index = QgsSpatialIndex()
            feat_dict = {}
            for f in feats:
                g = f.geometry()
                if not g or g.isEmpty():
                    continue
                spatial_index.addFeature(f)
                feat_dict[f.id()] = (f, g)

            already_checked = set()
            for fid, (feat, geom1) in feat_dict.items():
                rect = geom1.boundingBox()
                candidate_ids = spatial_index.intersects(rect)

                for nid in candidate_ids:
                    if nid == fid:
                        continue
                    pair = tuple(sorted((fid, nid)))
                    if pair in already_checked:
                        continue
                    already_checked.add(pair)

                    feat2, geom2 = feat_dict[nid]

                    inter = geom1.intersection(geom2)
                    if not inter or inter.isEmpty():
                        continue

                    inter_length = inter.length()
                    if inter_length <= 0:
                        continue

                    len1 = geom1.length()
                    len2 = geom2.length()

                    ratio1 = inter_length / len1
                    ratio2 = inter_length / len2

                    nom1 = feat.attribute("NOM") or f"ID {feat.id()}"
                    nom2 = feat2.attribute("NOM") or f"ID {feat2.id()}"

                    # Vérifie les cas
                    if ratio1 >= 0.99 and ratio2 >= 0.99:
                        msg += (f"\n🔴{layer.name()}: superposition totale "
                                f"entre '{nom1}' et '{nom2}'")
                        layer.selectByIds([fid, nid])
                    elif ratio1 >= 0.1 or ratio2 >= 0.1:
                        msg += (f"\n🟠 {layer.name()}: Superposition partielle "
                                f"entre '{nom1}' et '{nom2}' "
                                f"({ratio1*100:.1f}% / {ratio2*100:.1f}% recouvrement)")
                        layer.selectByIds([fid, nid])


        # Préparation pour distance géodésique
        d = QgsDistanceArea()
        d.setEllipsoid('WGS84')
        d.setSourceCrs(QgsCoordinateReferenceSystem("EPSG:4326"), project.transformContext())

        # Règles de distance minimale (intra-couche)
        # Format: (NomCouche, NomCouche, DistMin_mètres, (TypeVal1), (TypeVal2)) - types optionnels
        distance_rules = [
            ("Chambre", "Chambre", 1.0),
            ("Poteau", "Poteau", 1.0),
            ("Point Technique", "Point Technique", 5.0, "point immeuble", "point immeuble"),
            ("Point Technique", "Point Technique", 0.4, "point façade", "point façade"),
            ("Point Technique", "Point Technique", 1.0, "adduction armoire", "adduction armoire"),
            ("Point Technique", "Point Technique", 0.3, "adduction façade", "adduction façade"),
            ("Point Technique", "Point Technique", 0.3, "adduction site", "adduction site"),
            ("Point Technique", "Point Technique", 5.0, "adduction immeuble", "adduction immeuble"),
            # Ajouter d'autres règles ici
        ]

        for lay_name1, lay_name2, dist_min, *type_vals in distance_rules:
            if lay_name1 != lay_name2:
                continue  # On traite uniquement distances intra-couche ici

            layers = [layer for layer in layer_points.keys() if layer.name() == lay_name1]
            for layer in layers:
                feats = list(layer.getFeatures())
                spatial_index = QgsSpatialIndex()
                feat_dict = {}

                for feat in feats:
                    geom = feat.geometry()
                    if not geom or geom.isEmpty():
                        continue
                    spatial_index.addFeature(feat)
                    feat_dict[feat.id()] = (feat, geom)

                errors = []

                for feat, geom1 in feat_dict.values():
                    attr_type1 = None
                    # Vérifier type le cas échéant
                    if lay_name1 == "Point Technique" and len(type_vals) == 2:
                        attr_type1 = feat.attribute("TYPE")
                        if attr_type1 not in type_vals:
                            continue

                    center = geom1.boundingBox().center()
                    buffer = dist_min / 111320.0  # Approximate degree buffer (~epsg4326)
                    # Pour simplifier recherche spatiale: nous faisons un buffer en degrés approx.
                    rect = QgsRectangle(
                        center.x() - buffer,
                        center.y() - buffer,
                        center.x() + buffer,
                        center.y() + buffer
                    )

                    neighbors_ids = spatial_index.intersects(rect)

                    for nid in neighbors_ids:
                        if nid == feat.id():
                            continue
                        feat2, geom2 = feat_dict[nid]
                        attr_type2 = None
                        if lay_name1 == "Point Technique" and len(type_vals) == 2:
                            attr_type2 = feat2.attribute("TYPE")
                            if attr_type2 not in type_vals:
                                continue

                        # Calcul distance géodésique précise WGS84
                        distance = d.measureLine(geom1.asPoint(), geom2.asPoint())

                        if distance < dist_min:
                            nom1 = feat.attribute("NOM") or f"ID {feat.id()}"
                            nom2 = feat2.attribute("NOM") or f"ID {feat2.id()}"
                            errors.append((nom1, nom2, distance, layer.name(), dist_min))

                if errors:
                    feat_ids = set()
                    # Récupérer IDs des entités concernées pour sélectionner
                    for e in errors:
                        for f in feats:
                            if f.attribute("NOM") == e[0] or f.attribute("NOM") == e[1] or f.id() == e[0] or f.id() == e[1]:
                                feat_ids.add(f.id())
                    layer.selectByIds(list(feat_ids))
                    for nom1, nom2, dist, lname, dist_min_val in errors:
                        msg += (f"\n⚠️ Distance minimale non respectée "
                                f"dans couche {lname} : entre '{nom1}' et '{nom2}', "
                                f"distance {dist:.2f} m (minimum {dist_min_val} m)")

        if msg.strip():
            QMessageBox.information(None, "Doublons détectés", msg.strip())
        else:
            QMessageBox.information(None, "Doublons", "✅ Aucun doublon détecté.")



# ============================================================
# ============================================================
# ===============     Fonction 2: doublons de NOM et IDS    ===============
# ============================================================
# ============================================================

   
    def check_name_duplicates(self):
            from collections import defaultdict
            couches = QgsProject.instance().mapLayers().values()
            total = 0
            details = ""
            prefixes = {
                "Chambre": "Cham_",
                "Canalisation": "Canal_",
                "Tranchee": "Tran_",
                "Point Technique": "PT_",
                "Support": "Supp_",
                "Batiment": "Bati_"
            }

            for layer in couches:
                if not isinstance(layer, QgsVectorLayer):
                    continue
                fields_names = [f.name() for f in layer.fields()]
                if "NOM" not in fields_names and not any(f in fields_names for f in ["id", "ID", "Id"]):
                    continue

                nomdict = defaultdict(list)
                iddict = defaultdict(list)

                # Détection du champ d'id métier présent
                id_field_candidates = [f for f in ["id", "ID", "Id"] if f in fields_names]
                id_field = id_field_candidates[0] if id_field_candidates else None

                for feat in layer.getFeatures():
                    nom_value = feat["NOM"] if "NOM" in fields_names else None
                    if nom_value is not None:
                        nomdict[str(nom_value).strip()].append(feat.id())

                    if id_field:
                        id_val = feat[id_field]
                        if id_val is not None:
                            iddict[str(id_val).strip()].append(feat.id())

                dup_ids_nom = []
                dup_ids_id = []

                for val, ids in nomdict.items():
                    if len(ids) > 1:
                        dup_ids_nom.extend(ids)
                        details += f"🔁 '{val}' ×{len(ids)} dans {layer.name()} (champ NOM)\n"

                for val, ids in iddict.items():
                    if len(ids) > 1:
                        dup_ids_id.extend(ids)
                        details += f"🔂 '{val}' ×{len(ids)} fois dans la couche {layer.name()}\n"

                dup_ids = list(set(dup_ids_nom + dup_ids_id))

                if dup_ids:
                    total += len(dup_ids)
                    layer.removeSelection()
                    layer.selectByIds(dup_ids)

            if total > 0:
                r = QMessageBox.question(
                    None, "Doublons NOM/ID internes",
                    f"{total} entités doublons détectées :\n\n{details} \n Ces entités sont sélectionnées dans leur couche",
                )

            else:
                QMessageBox.information(None, "Doublons NOM/ID internes", "✅ Aucun doublon trouvé.")
            
            if total > 0:
                r = QMessageBox.question(
                    None, "Doublons NOM/ID internes",
                    f"{total} entités doublons détectées :\n\n{details} \nCes entités sont sélectionnées dans leur couche.\nVoulez-vous renommer ces entités ?",
                )
                if r == QMessageBox.Yes:
                    self.renommer_tous_les_noms()


    def renommer_tous_les_noms(self):

                    # Définitions des préfixes et couches
                    point_layers = {
                        'Chambre': 'Cham_',
                        'Point Technique': 'PT_',
                        'Poteau': 'Pot_',
                        'Batiment': 'Bati_'
                    }
                    line_layers = {
                        'Tranchee': 'Tran_',
                        'Canalisation': 'Canal_',
                        'Support': 'Supp_'
                    }
                    connexion_layers_info = [
                        ('Chambre', 'NOM'),
                        ('Point Technique', 'NOM'),
                        ('Poteau', 'NOM'),
                        ('Site', 'NOM'),
                        ('Point GC', 'id')
                    ]

                    def zero_pad(num, width=5):
                        return str(num).zfill(width)

                    # Demande directe à l'utilisateur
                    zr_value, ok = QInputDialog.getText(None, "Saisie NOM_ZR", "Entrez le nom de la ZR :")
                    if not ok or zr_value.strip() == "":
                        QMessageBox.warning(None, "Erreur", "❌ Valeur NOM_ZR non fournie. Opération annulée.")
                        return
                    zr_value = zr_value.strip()

                    # Fonction pour incrémenter le champ 'id' s'il existe dans une couche
                    def increment_id_if_exists(layer):
                        idx_id = layer.fields().indexFromName('id')
                        if idx_id == -1:
                            return  # Pas de champ 'id', on quitte
                        layer.startEditing()
                        i = 1
                        for feat in layer.getFeatures():
                            layer.changeAttributeValue(feat.id(), idx_id, i)
                            i += 1
                        layer.commitChanges()

                    # Renommage des points en fonction de NOM_ZR et prefix
                    def rename_points_with_nom_zr(zr_value):
                        for layer_name, prefix in point_layers.items():
                            layers = QgsProject.instance().mapLayersByName(layer_name)
                            if not layers:
                                QMessageBox.warning(None, "Attention", f"⚠️ Couche '{layer_name}' introuvable.")
                                continue
                            layer = layers[0]

                            # Incrémentation de l'attribut id si présent
                            increment_id_if_exists(layer)

                            layer.startEditing()
                            idx_nom = layer.fields().indexFromName('NOM')
                            idx_id = layer.fields().indexFromName('id')
                            for feat in layer.getFeatures():
                                # Utilisation de l'id comme compteur si il existe, sinon feat.id()+1
                                num = feat['id'] if idx_id != -1 else feat.id() + 1
                                new_nom = f"{zr_value}-{prefix}{zero_pad(num)}"
                                if idx_nom != -1:
                                    layer.changeAttributeValue(feat.id(), idx_nom, new_nom)
                            layer.commitChanges()

                    # Chargement des couches connexion avec champ pour rechercher nom point
                    loaded_connexion_layers = []
                    for name, champ in connexion_layers_info:
                        layers = QgsProject.instance().mapLayersByName(name)
                        if layers:
                            loaded_connexion_layers.append((layers[0], champ))
                        else:
                            QMessageBox.warning(None, "Attention", f"⚠️ Couche de point '{name}' introuvable.")

                    # Recherche du nom de connexion à partir d'un point
                    def get_connexion_name(point_geom):
                        for layer, field in loaded_connexion_layers:
                            for feat in layer.getFeatures():
                                if feat.geometry().contains(point_geom):
                                    value = feat[field]
                                    if value is None or str(value).strip() == '':
                                        QMessageBox.warning(None, "Erreur", f"❌ Une entité de '{layer.name()}' n’a pas de valeur dans le champ '{field}'.")
                                        layer.selectByIds([feat.id()])
                                        return None
                                    return str(value)
                        return None

                    # Renommage des lignes selon les noms des points de connexion
                    def rename_lignes():
                        for layer_name, prefix in line_layers.items():
                            layers = QgsProject.instance().mapLayersByName(layer_name)
                            if not layers:
                                QMessageBox.warning(None, "Attention", f"⚠️ Couche {layer_name} introuvable.")
                                continue
                            layer = layers[0]

                            # Incrémentation de l'attribut id si présent (optionnel, tu peux l'enlever si inutile pour les lignes)
                            increment_id_if_exists(layer)

                            erreurs = []
                            layer.startEditing()
                            idx_nom = layer.fields().indexFromName('NOM')
                            for feat in layer.getFeatures():
                                geom = feat.geometry()
                                if geom.isMultipart():
                                    line_points = geom.asMultiPolyline()[0]
                                else:
                                    line_points = geom.asPolyline()
                                if not line_points or len(line_points) < 2:
                                    continue
                                start_geom = QgsGeometry.fromPointXY(line_points[0])
                                end_geom = QgsGeometry.fromPointXY(line_points[-1])
                                nom_start = get_connexion_name(start_geom)
                                nom_end = get_connexion_name(end_geom)
                                if nom_start and nom_end:
                                    if nom_start != nom_end:
                                        new_nom = f"{prefix}{nom_start}-{nom_end}"
                                        if idx_nom != -1:
                                            layer.changeAttributeValue(feat.id(), idx_nom, new_nom)
                                else:
                                    erreurs.append(feat.id())
                            layer.commitChanges()
                            if erreurs:
                                layer.selectByIds(erreurs)
                                QMessageBox.warning(None, "Erreur", f"❌ {len(erreurs)} entité(s) mal connectée(s) dans la couche '{layer.name()}' (voir sélection).")

                    # Exécution complète
                    rename_points_with_nom_zr(zr_value)
                    rename_lignes()
                    QMessageBox.information(None, "Terminé", "Renommage des entités effectué avec succès.")

# ============================================================
# ============================================================
# ===============     Fonction 3: NULL VALUES    ===============
# ============================================================
# ============================================================

    def null_values(self):
        from collections import defaultdict, Counter
        root = QgsProject.instance().layerTreeRoot()
        grp = root.findGroup("Infrastructure")
        if not grp:
            QMessageBox.critical(None, "Erreur", "❌ Groupe 'Infrastructure' introuvable.")
            return
        autorise = {"MENAGE","COMMERCE","ENTREPRISE","ADMINISTRA","TOTAL PH"}
        rempl = {"REP","NOM_SR","PROJET"}
        total = 0
        tofill = defaultdict(lambda: defaultdict(list))
        manquants = defaultdict(lambda: defaultdict(int))  # <--- Ajout

        for node in grp.findLayers():
            layer = node.layer()
            if not isinstance(layer, QgsVectorLayer): continue
            champs = [f.name() for f in layer.fields()]
            ids = []
            for feat in layer.getFeatures():
                empties = []
                for ch in champs:
                    v = feat[ch]
                    empty = v is None or (isinstance(v,str) and not v.strip()) or str(v).strip().lower()=="null"
                    if empty and not (layer.name().lower()=="batiment" and ch in autorise):
                        empties.append(ch)
                        manquants[layer.name()][ch] += 1   # <--- Compte le nombre de valeurs manquantes par attribut
                        if ch in rempl:
                            tofill[layer.name()][ch].append(feat.id())
                if empties:
                    ids.append(feat.id())
                    total += 1
            layer.removeSelection()
            layer.selectByIds(ids)
        if total == 0:
            QMessageBox.information(None, "Remplir Attributs", "✅ PAS DE NULL VALUES.")
            return

        # => Création d'un message détaillant les vides par couche et attribut
        msg = f"🔍 {total} entités incomplètes sélectionnées.\n\n"
        msg += "Détail par couche et attribut :\n"
        for couche, attributs in manquants.items():
            for attr, n in attributs.items():
                msg += f"• {couche} : {attr} → {n} entités\n"

        QMessageBox.information(None, "Remplir Attributs", msg)

        if tofill:
            ok = QMessageBox.question(None, "Remplissage automatique",
                "Remplir REP, NOM_SR, PROJET avec la valeur la plus fréquente ?",
                QMessageBox.Yes|QMessageBox.No)
            if ok == QMessageBox.Yes:
                for lname, champs in tofill.items():
                    layer = QgsProject.instance().mapLayersByName(lname)[0]
                    layer.startEditing()
                    for ch, ids in champs.items():
                        vals = [str(f[ch]).strip() for f in layer.getFeatures() if f[ch] and str(f[ch]).strip().lower()!="null"]
                        if not vals: continue
                        maj = Counter(vals).most_common(1)[0][0]
                        idx = layer.fields().indexFromName(ch)
                        for fid in ids:
                            layer.changeAttributeValue(fid, idx, maj)
                    layer.commitChanges()
                QMessageBox.information(None, "Terminé", "✅ Champs remplis.")


# ============================================================
# ============================================================
# ===============     Fonction 4:  géometries fantomes  ===============
# ============================================================
# ============================================================

    def detecter_fantomes(self):
        noms = ['Chambre','Canalisation','Support', 'Tranchee', 'Poteau', 'Point Technique', 'point GC', 'Site', 'Batiment']
        project = QgsProject.instance()
        total = 0
        layers_f = {}
        msg = ""
        for nm in noms:
            couches = project.mapLayersByName(nm)
            if not couches: continue
            layer = couches[0]
            if not isinstance(layer,QgsVectorLayer) or not layer.isValid(): continue
            bad = []
            for feat in layer.getFeatures():
                g = feat.geometry()
                if g is None or g.isEmpty() or not g.isGeosValid():
                    bad.append(feat.id())
            if bad:
                total += len(bad)
                layers_f[layer] = bad
                layer.selectByIds(bad)
                msg += f"🧟 {len(bad)} entités fantômes dans {layer.name()}\n"
        if total > 0:
            r = QMessageBox.question(None, "Entités Fantômes",
                f"{msg}\nTotal: {total} entitées Fantômes. \nLes supprimer ?",
                QMessageBox.Yes|QMessageBox.No)
            if r == QMessageBox.Yes:
                for lyr, ids in layers_f.items():
                    lyr.startEditing()
                    for fid in ids:
                        lyr.deleteFeature(fid)
                    lyr.commitChanges()
                QMessageBox.information(None, "Suppression", f"✅ toutes les {total} entités Fantômes supprimées avec succès.")
            else:
                QMessageBox.information(None, "Annulé", "❌ Suppression annulée.")
        else:
            QMessageBox.information(None, "Fantômes", "✅ Aucune géométrie fantôme detectée .")


# ============================================================
# ============================================================
# ===============     Fonction 5 : fonction de l'accrochage ===============
# ============================================================
# ============================================================
# 

    def accrochage_lignes_points(self):
        from collections import defaultdict
        project = QgsProject.instance()
        tol = 0
        groupes = {
            'Infrastructure': {'points':['Chambre','Point Technique','Poteau','Point GC','Site'],
                            'lignes':['Canalisation','Support','Tranchee']},
            'Cuivre':         {'points':['SR','Manchon','PC'],
                            'lignes':['Cable Cuivre']},
            'Fibre Optique':  {'points':['SRO','Closer','BPE','PCO'],
                            'lignes':['Cable Fo']}
        }
        groupe, ok = QInputDialog.getItem(None, "Choisir groupe", "Groupe :", list(groupes.keys()), 0, False)
        if not ok: 
            return
        sel = groupes[groupe]

        # --- Charger tous les points ---
        pts = [(f.geometry().asPoint(), layer, f)
            for typ in ['points'] 
            for layer in [QgsProject.instance().mapLayersByName(n)[0]
                            for n in sel[typ] if QgsProject.instance().mapLayersByName(n)]
            for f in layer.getFeatures() if f.geometry() and f.geometry().type()==0]

        # --- Charger toutes les lignes ---
        lignes = [layer for n in sel['lignes'] if QgsProject.instance().mapLayersByName(n)
                for layer in [QgsProject.instance().mapLayersByName(n)[0]]]

        errs = []
        pts_connect = set()

        def est_connecte(pt, pts_aut):
            for p, lyr, feat in pts_aut:
                if QgsGeometry.fromPointXY(QgsPointXY(pt)).distance(QgsGeometry.fromPointXY(p)) <= tol:
                    pts_connect.add(feat.id())
                    return True
            return False

        for lyr in lignes:
            for f in lyr.getFeatures():
                g = f.geometry()
                if not g or g.type()!=1: 
                    continue
                poly = g.asMultiPolyline()[0] if g.isMultipart() else g.asPolyline()
                if len(poly)<2: 
                    continue
                start, end = poly[0], poly[-1]
                manq = []
                is_tr = "tranchee" in lyr.name().lower()

                # --- Filtrage spécial Canalisation ---
                if "canalisation" in lyr.name().lower():
                    # On exclut les Points GC
                    autor = [(p, l, ft) for (p, l, ft) in pts if "point gc" not in l.name().lower()]
                else:
                    autor = pts

                # Tolérance spéciale pour tranchée (autor = pts doublé, même logique qu’avant)
                if is_tr:
                    autor = autor + autor

                if not est_connecte(start, autor): 
                    manq.append("A")
                if not est_connecte(end, autor): 
                    manq.append("B")

                if manq:
                    nom = f['NOM'] if 'NOM' in f.fields().names() else f"{lyr.name()}_{f.id()}"
                    errs.append((lyr, f.id(), f"{nom} mal accrochée (extrémité {' et '.join(manq)})"))

        iso = []
        for p in pts:
            if p[2].id() in pts_connect: 
                continue
            iso.append((p[1], p[2].id(), p[2]['NOM'] if 'NOM' in p[2].fields().names() and p[2]['NOM'] else f"{p[1].name()}_{p[2].id()}"))

        sel_per = defaultdict(set)
        for lyr, fid, _ in errs+iso:
            sel_per[lyr].add(fid)
        for lyr, ids in sel_per.items():
            lyr.selectByIds(list(ids))

        if errs or iso:
            text = f"<b>⚠ Problèmes – {groupe}</b><br><br>"
            if errs:
                text += "<b>Lignes mal accrochées:</b><br>" + "<br>".join(f"• {e[2]}" for e in errs) + "<br><br>"
            if iso:
                text += "<b>Points isolés:</b><br>" + "<br>".join(f"• {p[2]}" for p in iso)
        else:
            text = f"✅ Tous connectés pour le groupe <b>{groupe}</b>."
        QMessageBox.information(None, "Accrochage", text)

# ============================================================
# ============================================================
# ===============     Fonction 6 : SUPERPOSITION TRANCHEE CANALISATION    ===============
# ============================================================
# ============================================================

    # 
    def verifier_tranchee_canalisation(self):
        try:
            nom_couche_canalisation = 'Canalisation'
            nom_couche_tranchee = 'Tranchee'

            couche_canalisation = QgsProject.instance().mapLayersByName(nom_couche_canalisation)
            couche_tranchee = QgsProject.instance().mapLayersByName(nom_couche_tranchee)

            if not couche_canalisation or not couche_tranchee:
                QMessageBox.critical(None, "Erreur", "❌ Vérifiez que les couches 'Canalisation' et 'Tranchée' sont bien chargées.")
                return

            couche_canalisation = couche_canalisation[0]
            couche_tranchee = couche_tranchee[0]

            index_tranchee = QgsSpatialIndex()
            features_tranchee = {}
            for feat in couche_tranchee.getFeatures():
                features_tranchee[feat.id()] = feat
                index_tranchee.insertFeature(feat)

            index_canalisation = QgsSpatialIndex()
            features_canalisation = {}
            for feat in couche_canalisation.getFeatures():
                features_canalisation[feat.id()] = feat
                index_canalisation.insertFeature(feat)

            erreurs_canalisation_hors = []
            erreurs_tranchee_en_excès = []

            couche_canalisation.removeSelection()
            couche_tranchee.removeSelection()

            # Vérification canalisations
            for feat_can in features_canalisation.values():
                geom_can = feat_can.geometry()
                intersects_ids = index_tranchee.intersects(geom_can.boundingBox())
                geoms_tranchee = [features_tranchee[fid].geometry() for fid in intersects_ids]

                if not geoms_tranchee:
                    erreurs_canalisation_hors.append(feat_can.id())
                    continue

                geom_union = geoms_tranchee[0]
                for g in geoms_tranchee[1:]:
                    geom_union = geom_union.combine(g)

                if not geom_union.contains(geom_can):
                    erreurs_canalisation_hors.append(feat_can.id())

            # Vérification tranchées
            for feat_tr in features_tranchee.values():
                geom_tr = feat_tr.geometry()
                intersects_ids = index_canalisation.intersects(geom_tr.boundingBox())
                geoms_canalisation = [features_canalisation[fid].geometry() for fid in intersects_ids]

                if not geoms_canalisation:
                    erreurs_tranchee_en_excès.append(feat_tr.id())
                    continue

                geom_union = geoms_canalisation[0]
                for g in geoms_canalisation[1:]:
                    geom_union = geom_union.combine(g)

                if not geom_union.contains(geom_tr):
                    erreurs_tranchee_en_excès.append(feat_tr.id())

            couche_canalisation.selectByIds(erreurs_canalisation_hors)
            couche_tranchee.selectByIds(erreurs_tranchee_en_excès)

            total_erreurs = len(erreurs_canalisation_hors) + len(erreurs_tranchee_en_excès)
            if total_erreurs == 0:
                QMessageBox.information(None, "CANAL SUR TRANCHEE", "✅ Tranchées et canalisations parfaitement superposées.")
            else:
                msg = "⚠️ Erreurs détectées dans la superposition :\n"
                if erreurs_canalisation_hors:
                    msg += f"\n❌ Canalisations partiellement ou totalement hors tranchée : {len(erreurs_canalisation_hors)}"
                if erreurs_tranchee_en_excès:
                    msg += f"\n❌ Tranchées en excès (dépassant les canalisations) : {len(erreurs_tranchee_en_excès)}"
                QMessageBox.warning(None, "Problèmes détectés", msg)

        except Exception as e:
            QMessageBox.critical(None, "Erreur", f"Une erreur est survenue :\n{str(e)}")

# ============================================================
# ============================================================
# ===============     Fonction 7: vérificateur de Type de Canalisation     ===============
# ============================================================
# ============================================================
 
    def verifier_type_canal(self):
        site_layer = self.get_layer_by_name("Site")
        canal_layer = self.get_layer_by_name("Canalisation")
        chambre_layer = self.get_layer_by_name("Chambre")
        pt_layer = self.get_layer_by_name("Point Technique")
        poteau_layer = self.get_layer_by_name("Poteau")

        if not canal_layer or not chambre_layer or not pt_layer or not poteau_layer:
            QMessageBox.warning(None, "Erreur", "Une ou plusieurs couches nécessaires sont absentes.")
            return

        def get_connected_type(point_geom):
            for f in chambre_layer.getFeatures():
                if f.geometry().intersects(point_geom):
                    return "Chambre", None
            for f in pt_layer.getFeatures():
                if f.geometry().intersects(point_geom):
                    return "Point Technique", f["TYPE"]
            for f in poteau_layer.getFeatures():
                if f.geometry().intersects(point_geom):
                    return "Poteau", None
            for f in site_layer.getFeatures():
                if f.geometry().intersects(point_geom):
                    return "Site", None
            return "Inconnu", None

        erreurs, ids_erreurs = [], []

        for feat in canal_layer.getFeatures():
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue

            start_geom = geom.interpolate(0)
            end_geom = geom.interpolate(geom.length())

            t1, extra1 = get_connected_type(start_geom)
            t2, extra2 = get_connected_type(end_geom)

            nom = feat["NOM"] or "Inconnu"
            current = feat["TYPE CANAL"]
            expected = None

            if t1 == t2 == "Chambre":
                expected = "Distribution"
            elif "Chambre" in [t1, t2] and "Point Technique" in [t1, t2]:
                for val in (extra1, extra2):
                    val = str(val).lower()
                    if "façade" in val:
                        expected = "Adduction Façade"
                    elif "immeuble" in val:
                        expected = "Adduction Immeuble"
                    elif "armoire" in val:
                        expected = "Distribution"
            elif "Chambre" in [t1, t2] and "Poteau" in [t1, t2]:
                expected = "Adduction Aérien"
            elif "Chambre" in [t1, t2] and "Site" in [t1, t2]:
                expected = "Distribution"

            if expected and current != expected:
                erreurs.append(f"→ {nom} entre {t1} et {t2} \n  Erreur : ❌'{current}' \n Solution: ✅'{expected}' ")
                ids_erreurs.append(feat.id())
            elif expected is None:
                erreurs.append(f"{nom} → Connexion inconnue entre {t1} et {t2} (TYPE CANAL = '{current}')")
                ids_erreurs.append(feat.id())

        canal_layer.removeSelection()
        if ids_erreurs:
            canal_layer.selectByIds(ids_erreurs)

        QMessageBox.information(None, "TYPE CANAL", "\n".join(erreurs) if erreurs else "✅ TYPE CANAL corrects.")

# ============================================================
# ============================================================
# ===============     Fonction 8: vérificateur de Type de supports    ===============
# ============================================================
# ============================================================
    def point_exact(self, point, couche):
        for feat in couche.getFeatures():
            geom = feat.geometry()
            if geom and geom.asPoint() == point:
                return feat
        return None

    def verifier_supports(self):
        couche_canal = self.get_layer_by_name("Canalisation")
        couche_support = self.get_layer_by_name("Support")
        couche_pts = self.get_layer_by_name("Point Technique")
        couche_poteau = self.get_layer_by_name("Poteau")

        if not couche_support or not couche_pts or not couche_poteau:
            QMessageBox.warning(None, "Erreur", "Les couches 'Support', 'Point Technique' ou 'Poteau' sont introuvables.")
            return

        ids_erreurs, erreurs = [], []

        # Fonction utilitaire pour vérifier le mot-clé dans le champ TYPE d'une entité
        def type_contains(feat, mot):
            return feat and 'TYPE' in feat.fields().names() and mot in str(feat['TYPE']).lower()

        for support in couche_support.getFeatures():
            geom = support.geometry()
            # Récupérer la liste des points du support (ligne)
            points = geom.asMultiPolyline()[0] if geom.isMultipart() else geom.asPolyline()
            if len(points) < 2:
                continue

            p1, p2 = QgsPointXY(points[0]), QgsPointXY(points[-1])
            pt1, pt2 = self.point_exact(p1, couche_pts), self.point_exact(p2, couche_pts)
            pot1, pot2 = self.point_exact(p1, couche_poteau), self.point_exact(p2, couche_poteau)

            support_nom = support['NOM']
            support_type = str(support['TYPE']).strip().lower()

            # === Vérification par type de support ===
            if support_type == "façade":
                if type_contains(pt1, "façade") and type_contains(pt2, "façade"):
                    pass
                else:
                    erreurs.append(f"❌ Support '{support_nom}' est de type Façade mais n’est pas entre deux points techniques 'Façade'.")
                    ids_erreurs.append(support.id())

            elif support_type == "immeuble":
                if type_contains(pt1, "immeuble") and type_contains(pt2, "immeuble"):
                    pass
                else:
                    erreurs.append(f"❌ Support '{support_nom}' est de type Immeuble mais n’est pas entre deux points techniques 'Immeuble'.")
                    ids_erreurs.append(support.id())
            elif support_type == "Saut de façade":
                if type_contains(pt1, "point façade") and type_contains(pt2, "point façade"):
                    pass
                else:
                    erreurs.append(f"❌ Support '{support_nom}' est de type Saut de façade mais n’est pas entre deux points techniques de type 'points façade'.")
                    ids_erreurs.append(support.id())


            elif support_type == "aérien":
                # Cas 1 : entre deux poteaux
                if pot1 and pot2:
                    pass
                # Cas 2 : entre un poteau et un point technique
                elif (pot1 and pt2) or (pot2 and pt1):
                    pass
                else:
                    erreurs.append(f"❌ Support '{support_nom}' est de type Aérien mais n’est pas entre poteaux ni entre un poteau et un point technique.")
                    ids_erreurs.append(support.id())

            else:
                erreurs.append(f"⚠️ Support '{support_nom}' a un type inconnu ou non géré : '{support_type}'.")
                ids_erreurs.append(support.id())

            # === Nouvelle règle générale : si c’est entre poteau et point technique, le support DOIT être aérien ===
            if (pot1 and pt2) or (pot2 and pt1):
                if support_type.lower() != "aérien":
                    erreurs.append(f"❌ Support '{support_nom}' va d’un poteau vers un point technique mais n’est PAS de type 'aérien'.")
                    ids_erreurs.append(support.id())

        couche_support.removeSelection()
        if ids_erreurs:
            couche_support.selectByIds(list(set(ids_erreurs)))

        if erreurs:
            QMessageBox.warning(None, "Vérification des supports", "\n".join(erreurs))
        else:
            QMessageBox.information(None, "Vérification des supports", "✅ TYPE Support corrects.")
    
# ============================================================
# ============================================================
# ===============     Fonction 9 : vérificateur de connectivité des chambres et des Canalisations     ===============
# ============================================================
# ============================================================

# 

    def verifier_connexions(self):
    # Dictionnaire complet des connexions autorisées
        connexion_valide = {
                "CPS1": ["CANIVEAU TYPE A", "CANIVEAU TYPE B", "PNS1", "PNS2", "PNS2C", "PN2","PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER",
                        "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L", "PNP5LC","PNP6", "PNP6C"],
                "CPS1M": ["CANIVEAU TYPE A", "CANIVEAU TYPE B", "PNS1", "PNS2", "PNS2C", "PN2",
                        "PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER","PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L", "PNP5LC",
                        "PNP6", "PNP6C"],
                "CPS1L": ["CANIVEAU TYPE A", "CANIVEAU TYPE B", "PNS1", "PNS2", "PNS2C", "PN2","PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER",
                        "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L", "PNP5LC","PNP6", "PNP6C"],
                "CPS2": ["CANIVEAU TYPE B", "PNS1", "PNS2", "PNS2C", "PN2",
                        "PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER", "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L", "PNP5LC",
                        "PNP6", "PNP6C"],
                "CPS2M": ["CANIVEAU TYPE B", "PNS1", "PNS2", "PNS2C", "PN2",
                        "PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER",
                        "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L", "PNP5LC",
                        "PNP6", "PNP6C"],
                "CPS2L": ["PNS1","PNS2", "PNS2C", "PN2", "PNS3", "PNS3C", "PNS3L", "PNS3LC",
                        "PN3", "PN3 TER", "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C",
                        "PNP5L", "PNP5LC", "PNP6", "PNP6C", "CANIVEAU TYPE B"],
                "CPS4": ["PNS2", "PNS2C", "PN2", "PNS3", "PNS3C", "PNS3L", "PNS3LC",
                        "PN3", "PN3 TER", "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C",
                        "PNP5L", "PNP5LC", "PNP6", "PNP6C"],
                "CPS4L": ["PNS2", "PNS2C", "PN2", "PNS3", "PNS3C", "PNS3L", "PNS3LC",
                        "PN3", "PN3 TER", "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C",
                        "PNP5L", "PNP5LC", "PNP6", "PNP6C"],
                "CPS4LBis": ["PNS2", "PNS2C", "PN2", "PNS3", "PNS3C", "PNS3L", "PNS3LC",
                            "PN3", "PN3 TER", "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C",
                            "PNP5L", "PNP5LC", "PNP6", "PNP6C"],
                "CPS4M": ["PNS2", "PNS2C", "PN2", "PNS3", "PNS3C", "PNS3L", "PNS3LC",
                            "PN3", "PN3 TER", "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C",
                            "PNP5L", "PNP5LC", "PNP6", "PNP6C"],     
                "CPS6"  :   ["PNS2", "PNS2C", "PN2", "PNS3", "PNS3C", "PNS3L", "PNS3LC",
                            "PN3", "PN3 TER", "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C",
                            "PNP5L", "PNP5LC", "PNP6", "PNP6C"],      

                "CPS6L"  :   ["PNS2", "PNS2C", "PN2", "PNS3", "PNS3C", "PNS3L", "PNS3LC",
                            "PN3", "PN3 TER", "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C",
                            "PNP5L", "PNP5LC", "PNP6", "PNP6C"],     

                "CPS6M"  :   ["PNS2", "PNS2C", "PN2", "PNS3", "PNS3C", "PNS3L", "PNS3LC",
                            "PN3", "PN3 TER", "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C",
                            "PNP5L", "PNP5LC", "PNP6", "PNP6C"],            

                "CPP9": ["PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER",
                        "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L", "PNP5LC",
                        "PNP6", "PNP6C"],
                "CPP9AC": ["PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER",
                        "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L", "PNP5LC",
                        "PNP6", "PNP6C"],

                "CPP9Bis": ["PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER",
                            "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L", "PNP5LC",
                            "PNP6", "PNP6C"],
                "CPP12": ["PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER",
                        "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L", "PNP5LC",
                        "PNP6", "PNP6C"],
                "CPP12A.L": ["PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER",
                        "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L", "PNP5LC",
                        "PNP6", "PNP6C"],
                
                "CPP12A.M": ["PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER",
                        "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L", "PNP5LC",
                        "PNP6", "PNP6C"],
                
                "CPP15B.L": ["PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER",
                        "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L", "PNP5LC",
                        "PNP6", "PNP6C"],

                "CPP15B.M": ["PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER",
                        "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L", "PNP5LC",
                        "PNP6", "PNP6C"],

                "CPP20" : ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],
                "CPP20B.L": ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],
                "CPP20B.M": ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],
                "CPP25": ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],
                "CPP25B.L":  ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],
                "CPP25B.M": ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],
                "CPP30": ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],
                "CPP30B.L": ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],
                "CPP30B.M": ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],
                "CPP35": ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],
                "CPP35B.L": ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],
                "CPP35B.M": ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],
                "CPP42": ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],
                "CPP42B.L": ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],
                "CPP42B.M": ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],
                "CPP49": ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],
                "CPP49B.L": ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],
                "CPP49B.M": ["PNP5","PNP5C","PNP5L","PNP5LC","PNP6","PNP6C"],

                "Buse de 10": ["Caniveau type A", "Caniveau type B", "PNS1", "PNS2", "PNS2C",
                            "PN2", "PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER",
                            "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L",
                            "PNP5LC", "PNP6", "PNP6C"],

                "Buse de 15": ["Caniveau type A", "Caniveau type B", "PNS1", "PNS2", "PNS2C",
                            "PN2", "PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER",
                            "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L",
                            "PNP5LC", "PNP6", "PNP6C"],

                "Buse de 20": ["Caniveau type A", "Caniveau type B", "PNS1", "PNS2", "PNS2C",
                            "PN2", "PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER",
                            "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L",
                            "PNP5LC", "PNP6", "PNP6C"],

                "Buse de 30": ["Caniveau type A", "Caniveau type B", "PNS1", "PNS2", "PNS2C",
                            "PN2", "PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER",
                            "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L",
                            "PNP5LC", "PNP6", "PNP6C"],
                
                "Basement 5": ["PNS3", "PNS3C", "PNS3L", "PNS3LC", "PN3", "PN3 TER",
                        "PNP4", "PNP4C", "PNP4L", "PNP4LC", "PNP5", "PNP5C", "PNP5L", "PNP5LC",
                        "PNP6", "PNP6C"], #aucune source je précise, c'est moi, Sylvius j'ai pris cet engagement en me basant que le CPP9 comme c'était le CPP9 on prenaait avant à la place de Basement 5

        }

        couche_can = self.get_layer_by_name("Canalisation")
        couche_ch = self.get_layer_by_name("Chambre")
        if not couche_can or not couche_ch:
            QMessageBox.warning(None, "Erreur", "Couches Canalisation ou Chambre manquantes.")
            return

        index_ch = QgsSpatialIndex(couche_ch.getFeatures())
        erreurs = []
        ids_erreurs_can = []
        ids_erreurs_ch = []

        for feat_can in couche_can.getFeatures():
            type_can = feat_can["TYPE CPS"]
            geom_can = feat_can.geometry()

            # Recherche des chambres en contact spatial
            ids_ch = index_ch.intersects(geom_can.boundingBox())
            for fid_ch in ids_ch:
                feat_ch = couche_ch.getFeature(fid_ch)
                if not geom_can.touches(feat_ch.geometry()):
                    continue
                type_ch = feat_ch["TYPE"]
                if type_can in connexion_valide:
                    if type_ch not in connexion_valide[type_can]:
                        erreurs.append(f"❌{type_can} ne correspond pas à {type_ch} ({feat_ch['NOM']} et {feat_can['NOM']})   ")
                        ids_erreurs_can.append(feat_can.id())
                        ids_erreurs_ch.append(feat_ch.id())
                else:
                    erreurs.append(f"{feat_can['NOM']} ({type_can}) → {feat_ch['NOM']} ({type_ch}) ❌ (type canalisation inconnu)")
                    ids_erreurs_can.append(feat_can.id())
                    ids_erreurs_ch.append(feat_ch.id())

        # Enlève les doublons d'IDs
        ids_erreurs_can = list(set(ids_erreurs_can))
        ids_erreurs_ch = list(set(ids_erreurs_ch))

        # Nettoyage des sélections précédentes
        couche_can.removeSelection()
        couche_ch.removeSelection()

        # Sélection des entités en erreur dans les deux couches
        if ids_erreurs_can:
            couche_can.selectByIds(ids_erreurs_can)
        if ids_erreurs_ch:
            couche_ch.selectByIds(ids_erreurs_ch)

        # Message à l'utilisateur
        if erreurs:
            QMessageBox.warning(None, "Connexions invalides", "\n".join(erreurs))
        else:
            QMessageBox.information(None, "Validation", "Toutes les connexions de chambres à canalisations sont valides ✅")

# ============================================================
# ============================================================
# ===============     Fonction 10: Vérificateur de CPS CANAL ET TRANC    ===============
# ============================================================
# ============================================================

    def verifier_cps_tranchee(self):
        layer_canal = self.get_layer_by_name("Canalisation")
        layer_tranch = self.get_layer_by_name("Tranchee")

        if not layer_canal or not layer_tranch:
            QMessageBox.warning(None, "Erreur", "Couches Canalisation ou Tranchée manquantes.")
            return

        index_tranch = QgsSpatialIndex(layer_tranch.getFeatures())
        erreurs = []
        ids_erreurs_canal = []
        ids_erreurs_tranch = []

        def types_compatibles(cps, tranch):
            # Cas où les types sont strictement égaux
            if cps == tranch:
                return True
            # Cas où la différence est uniquement un 'C' ajouté à la fin dans un des deux
            elif cps.endswith('C') and cps[:-1] == tranch:
                return True
            elif tranch.endswith('C') and tranch[:-1] == cps:
                return True
            else:
                return False

        for feat_canal in layer_canal.getFeatures():
            geom_canal = feat_canal.geometry()
            type_cps = str(feat_canal["TYPE CPS"]).strip().upper() if feat_canal["TYPE CPS"] else ""
            ids_tranch = index_tranch.intersects(geom_canal.boundingBox())
            for id_tr in ids_tranch:
                feat_tranch = layer_tranch.getFeature(id_tr)
                geom_tranch = feat_tranch.geometry()
                type_tranch = str(feat_tranch["TYPE TRANC"]).strip().upper() if feat_tranch["TYPE TRANC"] else ""

                inter_geom = geom_canal.intersection(geom_tranch)
                if inter_geom and not inter_geom.isEmpty() and inter_geom.length() > 0:
                    if not types_compatibles(type_cps, type_tranch):
                        erreurs.append(f"Canal '{feat_canal['NOM']}' ≠ Tranchée '{feat_tranch['NOM']}' → {type_cps} ≠ {type_tranch}")
                        ids_erreurs_canal.append(feat_canal.id())
                        ids_erreurs_tranch.append(feat_tranch.id())

        layer_canal.removeSelection()
        layer_tranch.removeSelection()
        if ids_erreurs_canal:
            layer_canal.selectByIds(list(set(ids_erreurs_canal)))
        if ids_erreurs_tranch:
            layer_tranch.selectByIds(list(set(ids_erreurs_tranch)))

        if erreurs:
            QMessageBox.warning(None, "Incohérences CPS vs Tranchée", "\n".join(erreurs))
        else:
            QMessageBox.information(None, "CPS CANAL/TRANCHEE", "✅ Types cohérents.")


# ============================================================
# ============================================================
# ===============     Fonction 11 : vérificateur de FONCTION des chambres     ===============
# ============================================================
# ============================================================

    def verifier_fonction_chambre(self):
        chambre_layer = self.get_layer_by_name("Chambre")
        canalisation_layer = self.get_layer_by_name("Canalisation")

        if not chambre_layer or not canalisation_layer:
            QMessageBox.warning(None, "Erreur", "Couches 'Chambre' ou 'Canalisation' manquantes.")
            return

        chambre_layer.removeSelection()
        canalisation_layer.removeSelection()

        index_canal = QgsSpatialIndex(canalisation_layer.getFeatures())

        chambre_erreurs_ids = []
        canalisation_associees_ids = []
        erreurs_messages = []

        for chambre in chambre_layer.getFeatures():
            fonction_actuelle = chambre["FONCTION"]

            # Exception : ignorer les chambres de départ
            if fonction_actuelle == "Chambre de départ":
                continue

            geom_chambre = chambre.geometry()

            ids_near = index_canal.intersects(geom_chambre.buffer(0.5, 1).boundingBox())

            count_distribution = 0
            canaux_distribution_ids = []

            for fid in ids_near:
                canal_feat = canalisation_layer.getFeature(fid)
                if canal_feat["TYPE CANAL"] != "Distribution":
                    continue

                geom_line = canal_feat.geometry()
                if geom_line.isMultipart():
                    line_points = geom_line.asMultiPolyline()[0]
                else:
                    line_points = geom_line.asPolyline()

                p1 = QgsPointXY(line_points[0])
                p2 = QgsPointXY(line_points[-1])

                if (geom_chambre.intersects(QgsGeometry.fromPointXY(p1)) or
                    geom_chambre.intersects(QgsGeometry.fromPointXY(p2))):
                    count_distribution += 1
                    canaux_distribution_ids.append(fid)

            if count_distribution == 0:
                continue

            if count_distribution >= 3:
                fonction_attendue = "Chambre de raccordement"
            elif count_distribution == 2:
                fonction_attendue = "Chambre de tirage"
            elif count_distribution == 1:
                fonction_attendue = "Chambre de Terminaison"
            else:
                fonction_attendue = None

            if fonction_actuelle != fonction_attendue:
                chambre_erreurs_ids.append(chambre.id())
                canalisation_associees_ids.extend(canaux_distribution_ids)
                nom_chambre = chambre["NOM"] if chambre["NOM"] else "(sans NOM)"
                erreurs_messages.append(
                    f"❌ Chambre '{nom_chambre}' a FONCTION '{fonction_actuelle}' mais devrait être '{fonction_attendue}' "
                    f"(canalisations Distribution : {count_distribution})"
                )

        chambre_layer.selectByIds(chambre_erreurs_ids)
        canalisation_layer.selectByIds(list(set(canalisation_associees_ids)))

        if erreurs_messages:
            QMessageBox.warning(
                None,
                "Vérification fonction chambre",
                "\n".join(erreurs_messages)
            )
        else:
            QMessageBox.information(
                None,
                "Vérification fonction chambre",
                "✅ Toutes les chambres ont une fonction correcte."
            )

# ============================================================
# ============================================================
# ===============     Fonction 11 : vérificateur de FONCTION des chambres     ===============
# ============================================================
# ============================================================

