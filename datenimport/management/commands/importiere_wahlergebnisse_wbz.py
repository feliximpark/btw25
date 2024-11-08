from django.core.management.base import BaseCommand
from ergebnisse_api.models import Wahlergebnis_WBZ
import pandas as pd
import os
from django.conf import settings

class Command(BaseCommand):
    help = '''
    Importiert Wahlergebnisse aus einer Excel-Datei, transformiert 
    die Daten und speichert sie in die Datenbank. Aufruf über Kommandozeile 
    (sheet-name ist optional): python manage.py importiere_wahlergebnisse_wbz daten/wahlergebnisse.xlsx --sheet "Sheet1"
    '''

    def add_arguments(self, parser):
        parser.add_argument('dateipfad', type=str, help='Pfad zur Excel-Datei')
        parser.add_argument('--sheet', type=str, default=None, help='Name des Excel-Sheets (optional)')

    def handle(self, *args, **kwargs):
        dateipfad = kwargs['dateipfad']
        sheet_name = kwargs.get('sheet')

        # Optional: Standard-Sheet festlegen, falls nicht angegeben
        if not sheet_name:
            sheet_name = 0  # Erstes Sheet

        try:
            # Vollständigen Pfad zur Datei ermitteln, falls relativer Pfad angegeben
            # verweist automatisch auf den Ordner "daten" im Projektverzeichnis
            if not os.path.isabs(dateipfad):
                dateipfad = os.path.join(settings.BASE_DIR, 'daten', dateipfad)

            # Excel-Datei einlesen mit angegebenem Sheet
            df = pd.read_excel(dateipfad, sheet_name=sheet_name)

            self.stdout.write(self.style.SUCCESS(f'Sheet "{sheet_name}" erfolgreich geladen.'))

            # Spalten ohne Postfix '_1' und '_2', die nicht transformiert werden sollen
            feste_spalten = [
                'Wahl', 'WK-Nr', 'WK-Name', 'Ebene', 'AGS', 'Ortname',
                'Briefwahl_Sonderfall', 'WBZ-Art', 'WBZ-Nr', 'WBZ-Name',
                'Wahlberechtigte', 'Wähler'
            ]

            # Spalten für ungueltige und gueltige Stimmen
            ungueltige_spalten = ['ungültige_1', 'ungültige_2']
            gueltige_spalten = ['gültige_1', 'gültige_2']

            # Identifizieren der Parteispalten
            partei_spalten = [spalte for spalte in df.columns if spalte not in feste_spalten]

            # Zusammenführen der ungueltige und gueltige Spalten
            ungueltige_melted = pd.melt(
                df,
                id_vars=feste_spalten,
                value_vars=ungueltige_spalten,
                var_name='Stimmart',
                value_name='ungueltige'
            )
            gueltige_melted = pd.melt(
                df,
                id_vars=feste_spalten,
                value_vars=gueltige_spalten,
                var_name='Stimmart',
                value_name='gueltige'
            )

            # Bereinige die Stimmart-Spalten
            ungueltige_melted['Stimmart'] = ungueltige_melted['Stimmart'].str[-1]
            gueltige_melted['Stimmart'] = gueltige_melted['Stimmart'].str[-1]


            # Zusammenführen der ungueltige und gueltige Daten
            df_votes = pd.merge(
                ungueltige_melted,
                gueltige_melted,
                on=feste_spalten + ['Stimmart']
            )

            # Melting der Parteistimmen
            stimmen_spalten = [spalte for spalte in partei_spalten if spalte.endswith('_1') or spalte.endswith('_2')]

            partei_stimmen = pd.melt(
                df,
                id_vars=feste_spalten,
                value_vars=stimmen_spalten,
                var_name='Partei_Stimmart',
                value_name='Stimmen'
            )

            # Extrahiere Partei und Stimmart aus 'Partei_Stimmart'
            partei_stimmen['Stimmart'] = partei_stimmen['Partei_Stimmart'].str[-1]
            partei_stimmen['Partei'] = partei_stimmen['Partei_Stimmart'].str[:-2]

            # Entferne die Hilfsspalte 'Partei_Stimmart'
            partei_stimmen.drop(columns=['Partei_Stimmart'], inplace=True)

            # Zusammenführen mit den ungueltige und gueltige Stimmen
            df_long = pd.merge(
                df_votes,
                partei_stimmen,
                on=feste_spalten + ['Stimmart'],
                how='left'
            )

            # Entferne Zeilen, in denen "Partei" den Wert "ungültige" oder "gültige" hat
            df_long = df_long[~df_long["Partei"].isin(["ungültige", "gültige"])]
            
            # Parteien entfernen, die im WBK/WK nicht angetreten sind
            df_long = df_long[df_long['Stimmen'] != "x"]

            # Füge die Partei hinzu
            df_long['Partei'] = df_long['Partei'].fillna('')

            # Konvertiere 'Stimmen' zu Integer
            df_long['Stimmen'] = df_long['Stimmen'].astype(int)
            
            # AGS kürzen wenn länger als 8 Stellen, dann das letzte Zeichen löschen
            df_long['AGS'] = df_long['AGS'].astype(str)
            df_long['AGS'] = df_long['AGS'].apply(lambda x: x[:-1] if len(x) > 8 else x)
            

            # NaN-Werte in 'Wahlberechtigte' bei Briefwahl auf 0 setzen
            df_long['Wahlberechtigte'] = df_long['Wahlberechtigte'].fillna(0).astype(int)
            df_long.to_clipboard(decimal=",", index=False)
            # Daten in die Datenbank speichern
            bulk_list = []
            for index, row in df_long.iterrows():
                bulk_list.append(Wahlergebnis_WBZ(
                    Wahl=row['Wahl'],
                    WKNr=row['WK-Nr'],
                    WKName=row['WK-Name'],
                    Ebene=row['Ebene'],
                    AGS=str(row['AGS']),
                    Ortname=row['Ortname'],
                    Briefwahl_Sonderfall=row.get('Briefwahl_Sonderfall', ''),
                    WBZArt=row['WBZ-Art'],
                    WBZNr=row['WBZ-Nr'],
                    WBZName=row['WBZ-Name'],
                    Wahlberechtigte=row['Wahlberechtigte'],
                    Wähler=row['Wähler'],
                    Stimmart=row['Stimmart'],
                    ungueltige=row['ungueltige'],
                    gueltige=row['gueltige'],
                    Partei=row['Partei'],
                    Stimmen=row['Stimmen'],
                ))

            # Bulk-Create in Paketen von 1000 Objekten
            BATCH_SIZE = 1000
            for i in range(0, len(bulk_list), BATCH_SIZE):
                Wahlergebnis_WBZ.objects.bulk_create(bulk_list[i:i+BATCH_SIZE], ignore_conflicts=True)
                self.stdout.write(self.style.SUCCESS(f'Datenpaket {i // BATCH_SIZE + 1} importiert.'))

            self.stdout.write(self.style.SUCCESS('Import erfolgreich abgeschlossen.'))

        except FileNotFoundError:
            self.stderr.write(self.style.ERROR('Die angegebene Datei wurde nicht gefunden.'))
        except ValueError as ve:
            self.stderr.write(self.style.ERROR(f'ValueError: {ve}'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Fehler beim Importieren: {e}'))
