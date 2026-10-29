# El período que mira un tablero (desde, hasta, inclusive) y contra qué se
# compara, más las cuentas de los indicadores (variación, margen, parte del
# total) con sus casos sin dato. Son reglas del negocio puras: cómo se define
# "el período anterior" y cuándo un porcentaje no tiene sentido.
# Acá NO se consulta la base ni se arma nada para mostrar.
from dataclasses import dataclass
from datetime import date, timedelta

from backend.dominio.excepciones import DatoInvalido

DIAS_POR_DEFECTO = 30          # sin fechas, un tablero mira los últimos 30 días
DIAS_MAXIMOS = 366             # más de un año no entra en un tablero
COMPARACIONES = ("anterior", "anio")


@dataclass(frozen=True)
class Periodo:
    desde: date
    hasta: date

    def __post_init__(self):
        if self.desde > self.hasta:
            raise DatoInvalido("La fecha desde no puede ser posterior a la fecha hasta")
        if self.dias > DIAS_MAXIMOS:
            raise DatoInvalido(f"El período no puede tener más de {DIAS_MAXIMOS} días")

    @classmethod
    def elegido(cls, desde=None, hasta=None, hoy=None):
        """El que pidió el usuario; lo que falte se completa: sin "hasta", hoy;
        sin "desde", los DIAS_POR_DEFECTO días que terminan en "hasta"."""
        hasta = hasta or hoy or date.today()
        return cls(desde or hasta - timedelta(days=DIAS_POR_DEFECTO - 1), hasta)

    @property
    def dias(self):
        return (self.hasta - self.desde).days + 1

    def dia(self, numero):
        """El día número (0, 1, 2...) del período."""
        return self.desde + timedelta(days=numero)

    def comparado(self, como):
        """Contra qué se compara: "anterior" = los mismos días justo antes (del
        1 al 29/10 → del 2/9 al 30/9); "anio" = las mismas fechas un año antes."""
        if como == "anterior":
            return Periodo(self.desde - timedelta(days=self.dias), self.desde - timedelta(days=1))
        if como == "anio":
            return Periodo(un_anio_antes(self.desde), un_anio_antes(self.hasta))
        raise DatoInvalido(f"Comparación '{como}' inválida. Opciones: {', '.join(COMPARACIONES)}")


def un_anio_antes(dia):
    # El 29/2 no existe el año anterior: se usa el 28/2
    try:
        return dia.replace(year=dia.year - 1)
    except ValueError:
        return dia.replace(year=dia.year - 1, day=28)


# --------------------------------------------------------------- Indicadores

def variacion(actual, anterior):
    """Crecimiento en %: ((actual / anterior) - 1) x 100. Si antes no hubo nada
    (o fue negativo), no hay contra qué comparar: None, nunca un "+100 %"
    o un infinito engañoso."""
    if anterior is None or anterior <= 0:
        return None
    return round((float(actual) / float(anterior) - 1) * 100, 1)


def margen(ganancia, ventas):
    """Margen bruto en %: ganancia / ventas x 100. Sin ventas, sin dato."""
    if not ventas or ventas <= 0:
        return None
    return round(float(ganancia) / float(ventas) * 100, 1)


def proporcion(parte, total):
    """Qué parte del total es (participación en %). Sin total, sin dato."""
    if not total or total <= 0:
        return None
    return round(float(parte) / float(total) * 100, 1)


def diferencia(actual, anterior):
    """Para porcentajes (el margen) se compara en puntos, no en %: pasar del
    20 % al 25 % es +5 puntos."""
    if actual is None or anterior is None:
        return None
    return round(actual - anterior, 1)
