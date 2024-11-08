
from django.db import models

class Wahlergebnis(models.Model):
    ort = models.CharField(max_length=100)
    partei = models.CharField(max_length=100)
    stimmen = models.IntegerField()
    prozentsatz = models.DecimalField(max_digits=5, decimal_places=2)
    aktualisiert_am = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.partei} in {self.ort}"