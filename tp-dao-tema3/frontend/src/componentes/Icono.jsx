// Íconos de la interfaz (lucide-react), pedidos por un nombre en castellano:
// las pantallas dicen qué quieren mostrar ("carrito", "camion") y acá se elige
// el dibujo. Así cambiar un ícono, o la librería, se hace en un solo lugar.
// Acá NO va lógica de ninguna entidad.
import {
  BadgeCheck, ChartColumn, Circle, CircleCheck, ClipboardList, Download, Handshake, House, Lock, LogOut,
  Package, PackageOpen, PartyPopper, Plug, Receipt, Search, ShieldCheck, ShoppingBasket, ShoppingCart, Sparkles,
  Sprout, Store, Tag, Timer, TriangleAlert, Trophy, Truck, Undo2, User, Wallet, Warehouse,
} from "lucide-react";

const ICONOS = {
  inicio: House,
  carrito: ShoppingCart,
  camion: Truck,
  caja: Package,
  grafico: ChartColumn,
  producto: ShoppingBasket,
  etiqueta: Tag,
  proveedor: Handshake,
  local: Store,
  cd: Warehouse,
  usuario: User,
  admin: ShieldCheck,
  buscar: Search,
  nuevo: Sparkles,
  conexion: Plug,
  empezar: Sprout,
  pedido: ClipboardList,
  alerta: TriangleAlert,
  listo: CircleCheck,
  festejo: PartyPopper,
  recibo: Receipt,
  precinto: Lock,
  recibir: PackageOpen,
  verificar: BadgeCheck,
  descargar: Download,
  salir: LogOut,
  plata: Wallet,
  trofeo: Trophy,
  reloj: Timer,
  devolucion: Undo2,
};

export default function Icono({ nombre, tamano = 20, className }) {
  const Dibujo = ICONOS[nombre] ?? Circle;
  return <Dibujo size={tamano} strokeWidth={1.9} className={className} aria-hidden="true" focusable="false" />;
}
