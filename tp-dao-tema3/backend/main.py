# Punto de entrada de la app: desde acá se arranca todo (se levanta la config,
# la conexión a la base y se registran las rutas de la api).
# Ojo: acá NO va lógica de negocio ni consultas SQL, solo el "enchufar" las piezas.
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.api import rutas_maestros
from backend.dominio.excepciones import DatoInvalido, EntidadDuplicada, ErrorDeNegocio, NoEncontrado
from backend.persistencia.conexion import crear_tablas

crear_tablas()  # crea las tablas si no existen

app = FastAPI(title="TP DAO - Tema 3")

# Traducción de errores del negocio a códigos HTTP, en un solo lugar
CODIGOS_HTTP = {
    NoEncontrado: 404,
    EntidadDuplicada: 409,
    DatoInvalido: 400,
}


@app.exception_handler(ErrorDeNegocio)
def manejar_error_de_negocio(request: Request, error: ErrorDeNegocio):
    codigo = CODIGOS_HTTP.get(type(error), 409)
    return JSONResponse(status_code=codigo, content={"detail": str(error)})


@app.get("/salud")
def salud():
    return {"ok": True}


app.include_router(rutas_maestros.router)
app.include_router(rutas_maestros.router_productos)