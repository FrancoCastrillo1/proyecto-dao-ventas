# TP DAO – Tema 3: Sistema de Ventas e Inventario

Sistema para un **Centro de Distribución (CD)** que abastece a varios **locales**:
maneja maestros, stock por ubicación, reposición CD → locales (pedidos, órdenes,
remitos y bultos) y ventas en los locales (cobros, comprobantes y devoluciones).

## Integrantes

- Apellido, Nombre – Legajo
- Apellido, Nombre – Legajo
- Apellido, Nombre – Legajo
- Apellido, Nombre – Legajo

## Organización del proyecto

```
tp-dao-tema3/
├── backend/          → todo el backend en Python, separado en capas
│   ├── dominio/      → clases del negocio puras (sin base de datos ni web)
│   ├── persistencia/ → acceso a SQLite con patrón DAO
│   ├── servicios/    → casos de uso: coordinan dominio + persistencia
│   ├── api/          → endpoints web, solo reciben pedidos y llaman a servicios
│   └── datos/        → scripts de datos de prueba
├── tests/            → pruebas con pytest de las reglas de negocio
└── frontend/         → interfaz de usuario (tecnología a definir)
```

La regla de oro: cada capa solo conoce a la de abajo.
`api` → `servicios` → `dominio` + `persistencia`. El dominio no conoce a nadie.

## Cómo levantar el proyecto

Se necesitan **Python 3.10+** y **Node 18+**. Todos los comandos se corren
desde la carpeta `tp-dao-tema3/`.

### 1. Backend (la primera vez)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt pytest
```

### 2. Backend (cada vez) — terminal 1

```powershell
.venv\Scripts\python -m uvicorn backend.main:app --reload
```

Queda en http://127.0.0.1:8000. En http://127.0.0.1:8000/docs está la
documentación interactiva de la api (Swagger).

### 3. Frontend — terminal 2

```powershell
cd frontend
npm install      # solo la primera vez
npm run dev
```

Abrir http://localhost:5173. El backend tiene que estar corriendo.

### Tests

```powershell
.venv\Scripts\python -m pytest
```
