from django.db import models

class Wahlergebnis_WBZ(models.Model):
    Wahl = models.CharField(max_length=7)
    WKNr = models.CharField(max_length=4)
    WKName = models.CharField(max_length=100)
    Ebene = models.CharField(max_length=10)
    AGS = models.CharField(max_length=8)
    Ortname = models.CharField(max_length=70)
    Briefwahl_Sonderfall = models.CharField(max_length=50, blank=True, null=True)
    WBZArt = models.CharField(max_length=70)
    WBZNr = models.CharField(max_length=50)
    WBZName = models.CharField(max_length=70)
    Wahlberechtigte = models.IntegerField()
    Wähler = models.IntegerField()
    Stimmart = models.CharField(max_length=1)
    ungueltige = models.IntegerField()
    gueltige = models.IntegerField()
    Partei = models.CharField(max_length=30)
    Stimmen = models.IntegerField()
    aktualisiert_am = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.Partei} in {self.Ortname} ({'Erststimme' if self.Stimmart == '1' else 'Zweitstimme'})"