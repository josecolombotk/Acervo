import { useState, useEffect, useCallback } from 'react';
import { api } from './api';

const fmt = s => (s ? s.split('-').reverse().join('/') : '');
const NAV = [['inicio', 'Inicio'], ['catalogo', 'Catálogo'], ['socios', 'Socios'], ['prestamos', 'Préstamos']];

function Modal({ title, onClose, children }) {
  return (<div className="ov" onClick={e => e.target === e.currentTarget && onClose()}>
    <div className="md"><h3>{title}</h3>{children}</div></div>);
}

function FormModal({ title, fields, initial = {}, onSave, onClose }) {
  const [v, setV] = useState(initial);
  const [e, setE] = useState('');
  const save = async () => {
    const falta = fields.find(f => f.req && !String(v[f.k] ?? '').trim());
    if (falta) return setE(`El campo «${falta.label}» es obligatorio.`);
    try { await onSave(v); } catch (x) { setE(x.message); }
  };
  return (<Modal title={title} onClose={onClose}>
    {fields.map(f => (<div className="f" key={f.k}><label>{f.label}{f.req && ' *'}</label>
      {f.options
        ? <select value={v[f.k] ?? ''} onChange={x => setV({ ...v, [f.k]: x.target.value })}><option value="">Seleccionar…</option>{f.options.map(o => <option key={o}>{o}</option>)}</select>
        : <input type={f.type || 'text'} value={v[f.k] ?? ''} onChange={x => setV({ ...v, [f.k]: x.target.value })} />}</div>))}
    <div className="err">{e}</div>
    <div className="row"><button className="btn" onClick={save}>Guardar</button><button className="btn dg" onClick={onClose}>Cancelar</button></div>
  </Modal>);
}

function Login({ onLogin }) {
  const [u, setU] = useState(''); const [p, setP] = useState(''); const [e, setE] = useState('');
  const go = async () => {
    if (!u.trim() || !p) return setE('Ingrese usuario y contraseña.');
    try { onLogin(await api('/login', 'POST', { username: u, password: p })); } catch (x) { setE(x.message); }
  };
  return (<div className="login"><div className="lbox"><h1>ACERVO</h1>
    <div className="f"><label>Usuario</label><input value={u} onChange={x => setU(x.target.value)} onKeyDown={x => x.key === 'Enter' && go()} /></div>
    <div className="f"><label>Contraseña</label><input type="password" value={p} onChange={x => setP(x.target.value)} onKeyDown={x => x.key === 'Enter' && go()} /></div>
    <div className="err">{e}</div><button className="btn" style={{ width: '100%' }} onClick={go}>Iniciar sesión</button></div></div>);
}

function Vencidos({ lista, isB, onAviso }) {
  return (<div className="tw"><table><thead><tr><th>Socio</th><th>Ejemplar</th><th>Fecha vencimiento</th><th>Días de atraso</th><th></th></tr></thead><tbody>
    {lista.length ? lista.map(x => (<tr key={x.id_prestamo}><td>{x.socio}</td><td>{x.titulo}</td><td>{fmt(x.fecha_vencimiento)}</td>
      <td><span className="tag r">{x.dias_atraso}</span></td>
      <td>{isB && <button className="btn sm" onClick={() => onAviso(x.id_prestamo)}>Generar aviso{x.avisado ? ' ✓' : ''}</button>}</td></tr>))
      : <tr><td colSpan="5" className="empty">No hay préstamos vencidos</td></tr>}</tbody></table></div>);
}

function Dashboard({ isB, go, setBusq, aviso }) {
  const [d, setD] = useState(null); const [q, setQ] = useState('');
  useEffect(() => { api('/dashboard').then(setD).catch(() => {}); }, []);
  if (!d) return <p>Cargando…</p>;
  const C = ({ t, n, red }) => <div className={'card' + (red ? ' red' : '')}>{t}<strong>{n}</strong></div>;
  return (<>
    <input aria-label="Buscar libros desde el inicio" placeholder="Buscar por título, autor o categoría (Enter para buscar)" value={q} onChange={e => setQ(e.target.value)}
      onKeyDown={e => { if (e.key === 'Enter') { setBusq(q); go('catalogo'); } }} />
    <div className="cards"><C t="Ejemplares disponibles" n={d.disponibles} /><C t="Ejemplares prestados" n={d.prestados} /><C t="Préstamos activos" n={d.activos} />
      <C t="Préstamos vencidos" n={d.vencidos} red /><C t="Socios habilitados" n={d.socios} /></div>
    <h3>Accesos rápidos</h3>
    <div className="row" style={{ marginTop: 8 }}>
      <button className="btn" onClick={() => go('prestamos')}>Registrar préstamo</button>
      <button className="btn" onClick={() => go('prestamos')}>Registrar devolución</button>
      {isB && <button className="btn" onClick={() => go('socios', 'nuevo')}>Nuevo socio</button>}</div>
    <div className="sec"><h3>Préstamos vencidos</h3><a style={{ color: 'var(--mu)', cursor: 'pointer' }} onClick={() => go('prestamos')}>Ver todos</a></div>
    <Vencidos lista={d.vencidos_lista} isB={isB} onAviso={aviso} /></>);
}

const LIBRO_F = [{ k: 'titulo', label: 'Título', req: 1 }, { k: 'autor', label: 'Autor', req: 1 }, { k: 'categoria', label: 'Categoría', req: 1 },
  { k: 'ubicacion_fisica', label: 'Ubicación', req: 1 }, { k: 'editorial', label: 'Editorial' }, { k: 'isbn', label: 'ISBN' }];

function Catalogo({ isB, busq, toast }) {
  const [q, setQ] = useState(busq || ''); const [rows, setRows] = useState([]); const [m, setM] = useState(null);
  const load = useCallback(() => api('/libros?q=' + encodeURIComponent(q)).then(setRows).catch(x => toast(x.message)), [q]);
  useEffect(() => { load(); }, [load]);
  const baja = async l => {
    if (!window.confirm(`¿Dar de baja «${l.titulo}»? Se conserva el historial.`)) return;
    try { await api('/libros/' + l.id_libro, 'DELETE'); toast('Libro dado de baja'); load(); } catch (x) { toast(x.message); }
  };
  return (<>
    <div className="row" style={{ justifyContent: 'space-between' }}><h2>Catálogo</h2>{isB && <button className="btn" onClick={() => setM({})}>Nuevo libro</button>}</div>
    <div style={{ margin: '12px 0' }}><input aria-label="Buscar en el catálogo" placeholder="Buscar por título, autor o categoría" value={q} onChange={e => setQ(e.target.value)} /></div>
    <div className="tw"><table><thead><tr><th>Título</th><th>Autor</th><th>Categoría</th><th>Ejemplares</th><th>Disponibles</th><th>Ubicación</th>{isB && <th></th>}</tr></thead><tbody>
      {rows.length ? rows.map(l => (<tr key={l.id_libro}><td>{l.titulo}</td><td>{l.autor}</td><td>{l.categoria}</td><td>{l.ejemplares}</td>
        <td><span className={'tag' + (l.disponibles ? '' : ' r')}>{l.disponibles}</span></td><td>{l.ubicacion_fisica}</td>
        {isB && <td><div className="row"><button className="btn sm" onClick={() => setM(l)}>Editar</button><button className="btn sm dg" onClick={() => baja(l)}>Baja</button></div></td>}</tr>))
        : <tr><td colSpan="7" className="empty">Sin resultados</td></tr>}</tbody></table></div>
    {m && <FormModal title={m.id_libro ? 'Editar libro' : 'Nuevo libro'} initial={m} onClose={() => setM(null)}
      fields={m.id_libro ? LIBRO_F : [...LIBRO_F, { k: 'cantidad', label: 'Cantidad de ejemplares', type: 'number' }]}
      onSave={async v => { m.id_libro ? await api('/libros/' + m.id_libro, 'PUT', v) : await api('/libros', 'POST', v); setM(null); toast('Libro guardado'); load(); }} />}</>);
}

const SOCIO_F = [{ k: 'nombre', label: 'Nombre', req: 1 }, { k: 'apellido', label: 'Apellido', req: 1 }, { k: 'dni', label: 'DNI', req: 1 },
  { k: 'tipo_socio', label: 'Tipo de socio', req: 1, options: ['Afiliado CEC', 'Particular'] }, { k: 'nro_afiliado', label: 'N.º de afiliado (solo afiliados)' },
  { k: 'telefono', label: 'Teléfono' }, { k: 'email', label: 'Email' }];

function Socios({ isB, toast, abrirNuevo }) {
  const [q, setQ] = useState(''); const [rows, setRows] = useState([]); const [sel, setSel] = useState(null);
  const [hist, setHist] = useState([]); const [m, setM] = useState(abrirNuevo ? {} : null);
  const load = useCallback(() => api('/socios?q=' + encodeURIComponent(q)).then(setRows).catch(x => toast(x.message)), [q]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { sel ? api(`/socios/${sel.id_socio}/prestamos`).then(setHist).catch(() => {}) : setHist([]); }, [sel]);
  const cur = rows.find(r => r.id_socio === sel?.id_socio) || sel;
  const baja = async () => {
    if (!window.confirm(`¿Dar de baja (inhabilitar) a ${cur.nombre} ${cur.apellido}?`)) return;
    try { await api('/socios/' + cur.id_socio, 'DELETE'); toast('Socio inhabilitado'); load(); } catch (x) { toast(x.message); }
  };
  const habilitar = async () => { try { await api('/socios/' + cur.id_socio, 'PUT', { estado: 'Habilitado' }); toast('Socio habilitado'); load(); } catch (x) { toast(x.message); } };
  return (<>
    <div className="row" style={{ justifyContent: 'space-between' }}><h2>Gestión de socios</h2>{isB && <button className="btn" onClick={() => setM({})}>Nuevo socio</button>}</div>
    <div style={{ marginTop: 12 }}><input aria-label="Buscar socios" placeholder="Buscar por DNI / N.º de afiliado / nombre" value={q} onChange={e => setQ(e.target.value)} /></div>
    <div className="two"><div><h3 style={{ marginBottom: 8 }}>Listado</h3><div className="panel" style={{ padding: 0 }}>
      {rows.length ? rows.map(s => (<div key={s.id_socio} className={'li' + (s.id_socio === cur?.id_socio ? ' on' : '')} onClick={() => setSel(s)}>
        {s.apellido}, {s.nombre}<small>DNI {s.dni} · {s.tipo_socio}</small></div>)) : <div className="empty">Sin resultados</div>}</div></div>
      <div><h3 style={{ marginBottom: 8 }}>Ficha del socio</h3><div className="panel">{!cur ? <div className="empty">Seleccioná un socio</div> : (<>
        <div className="kv"><b>Nombre y apellido:</b>{cur.nombre} {cur.apellido}</div><div className="kv"><b>DNI:</b>{cur.dni}</div>
        <div className="kv"><b>Tipo de socio:</b>{cur.tipo_socio}{cur.nro_afiliado && ` (${cur.nro_afiliado})`}</div>
        <div className="kv"><b>Contacto:</b>{cur.telefono || '—'} {cur.email || ''}</div>
        <div className="kv"><b>Estado:</b><span className={'tag' + (cur.estado === 'Habilitado' ? '' : ' r')}>{cur.estado}</span></div>
        <div className="kv" style={{ display: 'block' }}><b>Préstamos ({cur.prestamos_activos} activos):</b>
          {hist.length ? hist.map(h => <div key={h.id_prestamo} style={{ padding: '3px 0' }}>{h.titulo} — {fmt(h.fecha_salida)} → {h.fecha_devolucion ? fmt(h.fecha_devolucion) : 'vence ' + fmt(h.fecha_vencimiento)} <span className={'tag' + (h.estado === 'Vencido' ? ' r' : '')}>{h.estado}</span></div>) : <div style={{ color: 'var(--mu)' }}>Sin historial</div>}</div>
        {isB && <div className="row" style={{ marginTop: 12 }}><button className="btn sm" onClick={() => setM(cur)}>Editar</button>
          {cur.estado === 'Habilitado' ? <button className="btn sm dg" onClick={baja}>Dar de baja</button> : <button className="btn sm" onClick={habilitar}>Habilitar</button>}</div>}</>)}</div></div></div>
    {m && <FormModal title={m.id_socio ? 'Editar socio' : 'Nuevo socio'} initial={m} fields={SOCIO_F} onClose={() => setM(null)}
      onSave={async v => { m.id_socio ? await api('/socios/' + m.id_socio, 'PUT', v) : await api('/socios', 'POST', v); setM(null); toast('Socio guardado'); load(); }} />}</>);
}

function Prestamos({ isB, toast, aviso }) {
  const [dni, setDni] = useState(''); const [cod, setCod] = useState(''); const [rows, setRows] = useState([]);
  const load = useCallback(() => api('/prestamos').then(setRows).catch(x => toast(x.message)), []);
  useEffect(() => { load(); }, [load]);
  const hoy = new Date(); const v = new Date(); v.setDate(v.getDate() + 15);
  const reg = async () => {
    if (!dni.trim() || !cod.trim()) return toast('Ingrese el DNI del socio y el código del ejemplar.');
    try { const r = await api('/prestamos', 'POST', { dni, codigo_inventario: cod }); toast('Préstamo registrado. Vence ' + fmt(r.fecha_vencimiento)); setDni(''); setCod(''); load(); }
    catch (x) { toast(x.message); }
  };
  const dev = async p => {
    if (!window.confirm(`¿Registrar la devolución de «${p.titulo}»?`)) return;
    try { await api(`/prestamos/${p.id_prestamo}/devolucion`, 'POST'); toast('Devolución registrada'); load(); } catch (x) { toast(x.message); }
  };
  const act = rows.filter(r => r.estado !== 'Devuelto'); const ven = act.filter(r => r.estado === 'Vencido');
  return (<>
    <h2>Préstamos</h2>
    <div className="panel" style={{ marginTop: 12 }}><div className="form"><div><label>DNI del socio</label><input value={dni} onChange={e => setDni(e.target.value)} /></div>
      <div><label>Código del ejemplar</label><input value={cod} placeholder="Ej: L0002-1" onChange={e => setCod(e.target.value)} /></div></div>
      <div>Fecha de salida: <b>hoy ({hoy.toLocaleDateString('es-AR')})</b></div><div>Vencimiento: <b>+15 días ({v.toLocaleDateString('es-AR')})</b></div>
      <div style={{ marginTop: 12 }}><button className="btn" onClick={reg}>Registrar</button></div></div>
    <div className="sec"><h3>Préstamos vencidos</h3></div>
    <Vencidos lista={ven.map(r => ({ ...r, avisado: 0 }))} isB={isB} onAviso={aviso} />
    <div className="sec"><h3>Préstamos activos</h3></div>
    <div className="tw"><table><thead><tr><th>Socio</th><th>Ejemplar</th><th>Código</th><th>Salida</th><th>Vence</th><th></th></tr></thead><tbody>
      {act.length ? act.map(p => (<tr key={p.id_prestamo}><td>{p.socio}</td><td>{p.titulo}</td><td>{p.codigo_inventario}</td><td>{fmt(p.fecha_salida)}</td>
        <td>{fmt(p.fecha_vencimiento)} {p.estado === 'Vencido' && <span className="tag r">vencido</span>}</td>
        <td><button className="btn sm" onClick={() => dev(p)}>Devolver</button></td></tr>)) : <tr><td colSpan="6" className="empty">Sin préstamos activos</td></tr>}</tbody></table></div></>);
}

export default function App() {
  const [user, setUser] = useState(undefined); const [view, setView] = useState('inicio'); const [busq, setBusq] = useState('');
  const [nuevo, setNuevo] = useState(false); const [msg, setMsg] = useState(''); const [av, setAv] = useState(null);
  useEffect(() => { api('/me').then(setUser).catch(() => setUser(null)); }, []);
  useEffect(() => { if (!msg) return; const t = setTimeout(() => setMsg(''), 3500); return () => clearTimeout(t); }, [msg]);
  if (user === undefined) return null;
  if (!user) return <Login onLogin={u => { setUser(u); setView('inicio'); }} />;
  const isB = user.rol === 'Bibliotecaria';
  const go = (v, extra) => { setNuevo(extra === 'nuevo'); setView(v); };
  const aviso = async id => {
    try { const r = await api(`/prestamos/${id}/aviso`, 'POST'); setAv(r.texto); } catch (x) { setMsg(x.message); }
  };
  const copiar = () => { navigator.clipboard?.writeText(av); setMsg('Texto copiado'); };
  const props = { isB, toast: setMsg, aviso };
  return (<>
    <header><b>ACERVO</b><div><span>{user.nombre} ({user.rol})</span> | <a onClick={async () => { await api('/logout', 'POST'); setUser(null); }}>Cerrar sesión</a></div></header>
    <div className="lay"><nav>{NAV.map(([k, t]) => <button key={k} className={view === k ? 'on' : ''} onClick={() => go(k)}>{t}</button>)}</nav>
      <main>
        {view === 'inicio' && <Dashboard {...props} go={go} setBusq={setBusq} />}
        {view === 'catalogo' && <Catalogo {...props} busq={busq} />}
        {view === 'socios' && <Socios {...props} abrirNuevo={nuevo} />}
        {view === 'prestamos' && <Prestamos {...props} />}
      </main></div>
    {av && <Modal title="Aviso de vencimiento" onClose={() => setAv(null)}><textarea readOnly value={av} />
      <div className="row" style={{ marginTop: 12 }}><button className="btn" onClick={copiar}>Copiar texto</button><button className="btn dg" onClick={() => setAv(null)}>Cerrar</button></div></Modal>}
    {msg && <div id="toast">{msg}</div>}</>);
}
