from qgis.PyQt.QtWidgets import QAction, QMenu, QMessageBox, QInputDialog
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProject, QgsVectorLayer, QgsWkbTypes, QgsSpatialIndex
import os


from .main import MonPlugin


class MonPlugIn_(MonPlugin):
    def __init__(self, iface):
        super().__init__(iface)  

    def initGui(self):
        super().initGui()
        
     # séparateur visuel
        self.menu.addSeparator()

        actions = [
            ("TOTAL CONTROL", self.run_all_checks),  
             ("NOMBRE d'entités par couches",self.verifier_couches_groupes),  
        ]
        for label, func in actions:
            action = QAction(label, self.iface.mainWindow())
            action.triggered.connect(func)
            self.menu.addAction(action)

    # Ici tu ajoutes tes fonctions spécifiques Manager


    def run_all_checks(self):
        """
        Exécute tous les contrôles en séquence
        """
        controles = [
            self.null_values,
            self.check_name_duplicates,
            self.check_geometry_duplicates,
            self.accrochage_lignes_points,
            self.detecter_fantomes,
            self.verifier_tranchee_canalisation,
            self.verifier_type_canal,
            self.verifier_supports,
            self.verifier_connexions,
            self.verifier_cps_tranchee,
            self.verifier_fonction_chambre,
        ]

        erreurs = []
        for controle in controles:
            try:
                controle()
            except Exception as e:
                erreurs.append(f"{controle.__name__} → {str(e)}")

        if erreurs:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "⚠ Résultats Vérification",
                "Certains contrôles ont échoué :\n" + "\n".join(erreurs)
            )
        else:
            QMessageBox.information(
                self.iface.mainWindow(),
                "✅ Résultats Vérification",
                "Tous les contrôles ont été exécutés avec succès."
            )



    def verifier_couches_groupes(self):

        # Définition des groupes et leurs couches
        groupes = {
            'Infrastructure': ['Canalisation','Chambre','Point Technique','Poteau','Point GC','Site','Batiment'],
            'Cuivre': ['Cable Cuivre','SR','Manchon','PC'],
            'Fibre Optique': ['Cable Fo','SRO','Closer','BPE','PCO']
        }

        # Demande du groupe à vérifier
        groupe, ok = QInputDialog.getItem(None, "Choix du groupe", "Quel groupe veux-tu vérifier ?", list(groupes.keys()), 0, False)
        if not ok:
            return

        couches_cible = groupes[groupe]
        project = QgsProject.instance()

        rapport = f"<b>🔎 Vérification des couches pour le groupe '{groupe}' :</b><br><br>"

        for nom in couches_cible:
            layers = project.mapLayersByName(nom)
            if not layers:
                rapport += f"⚠ La couche <b>{nom}</b> est introuvable dans le projet.<br>"
                continue

            layer = layers[0]

            # Vérifier que c'est une couche vecteur
            if not isinstance(layer, QgsVectorLayer):
                rapport += f"ℹ La couche <b>{nom}</b> n'est pas vectorielle (ignorée).<br>"
                continue

            count = layer.featureCount()

            if count == 0:
                rapport += f"⚠ La couche <b>{nom}</b> ne contient aucune entité !<br>"
            else:
                rapport += f"✅ La couche <b>{nom}</b> contient {count} entité(s).<br>"

            # Cas particulier pour Batiment
            if nom.lower() == 'batiment' and count < 100:
                rapport += f"⚠ J'ai remarqué qu'il y a peu de bâtiments ({count}), tu confirmes que c'est bien le cas ?<br>"


        # Affichage résultat
        QMessageBox.information(None, "Vérification des couches", rapport)


