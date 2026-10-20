// Productos y ubicaciones que usan las pantallas de procesos para mostrar
// nombres en vez de ids y para llenar los desplegables. Se cargan una vez por
// pantalla (incluidos los dados de baja, para poder nombrar operaciones viejas).
import { useEffect, useState } from "react";

import { api } from "../api.js";

export function useCatalogos() {
  const [productos, setProductos] = useState([]);
  const [ubicaciones, setUbicaciones] = useState([]);

  async function recargar() {
    try {
      setProductos(await api.listar("/productos?incluir_bajas=true"));
      setUbicaciones(await api.listar("/ubicaciones?incluir_bajas=true"));
    } catch {
      // Si falla, las pantallas muestran los ids; el error real lo informa cada acción
    }
  }
  useEffect(() => { recargar(); }, []);

  const producto = (id) => productos.find((p) => p.id === id);
  const ubicacion = (id) => ubicaciones.find((u) => u.id === id);

  return {
    productos,
    productosActivos: productos.filter((p) => p.activo),
    sucursales: ubicaciones.filter((u) => u.activo && u.puede_recibir),
    ubicacionesActivas: ubicaciones.filter((u) => u.activo),
    nombreProducto: (id) => producto(id)?.nombre ?? `Producto #${id}`,
    nombreUbicacion: (id) => ubicacion(id)?.nombre ?? `Ubicación #${id}`,
    ubicacion,
    recargar,
  };
}
