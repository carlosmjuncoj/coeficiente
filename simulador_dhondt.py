# simulador_dhondt.py (versión Cloud-safe con formulario + IDs estables)
# - Edición dentro de st.form("editor") con botón "Aplicar cambios"
# - Previene el bug "solo actualiza a la segunda" en Streamlit Cloud
# - 10 partidos por defecto (1000 votos c/u), 30 escaños por defecto
# - Matriz de cocientes 1..N (N=escaños) con top-N resaltado

import hashlib
import io
import uuid
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="Simulador D'Hondt (Perú)", page_icon="🧮", layout="wide")
st.title("🧮 Simulador de Cifra Repartidora (D’Hondt) – Perú")

# ---------- base inicial ----------
BASE_ROWS = [
    {"Partido": "Fuerza Popular",  "Votos": 1000},
    {"Partido": "Peru Libre",      "Votos": 1000},
    {"Partido": "Renovación",      "Votos": 1000},
    {"Partido": "Accion Popular",  "Votos": 1000},
    {"Partido": "Podemos Perú",    "Votos": 1000},
    {"Partido": "Partido 6",       "Votos": 1000},
    {"Partido": "Partido 7",       "Votos": 1000},
    {"Partido": "Partido 8",       "Votos": 1000},
    {"Partido": "Partido 9",       "Votos": 1000},
    {"Partido": "Partido 10",      "Votos": 1000},
]
REQUIRED_COLS = ["Partido", "Votos"]

def _mk_row(partido="", votos=0):
    return {"id": str(uuid.uuid4()), "Partido": partido, "Votos": int(votos)}

def _init_rows_with_ids():
    return [{**_mk_row(r["Partido"], r["Votos"])} for r in BASE_ROWS]

# ---------- estado ----------
if "rows" not in st.session_state:
    st.session_state.rows = _init_rows_with_ids()

# upgrade estados antiguos sin id
for r in st.session_state.rows:
    if "id" not in r:
        r["id"] = str(uuid.uuid4())

# ---------- utilidades ----------
def sanitize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "Partido" not in df.columns: df["Partido"] = ""
    if "Votos" not in df.columns:   df["Votos"] = 0
    df["Partido"] = df["Partido"].fillna("").astype(str)
    df["Votos"]   = pd.to_numeric(df["Votos"], errors="coerce").fillna(0).clip(lower=0).round().astype(int)
    return df[REQUIRED_COLS]

def dhondt(df_: pd.DataFrame, seats_: int):
    if df_.empty or seats_ <= 0:
        return pd.Series(dtype=int), pd.DataFrame(columns=["Partido","Divisor","Cociente","Rank","GanaEscaño"])
    rows = []
    for idx, r in df_.iterrows():
        v = int(r["Votos"])
        for d in range(1, seats_ + 1):
            rows.append({"idx": idx, "Partido": r["Partido"], "Divisor": d, "Cociente": v / d})
    q = pd.DataFrame(rows).sort_values("Cociente", ascending=False, ignore_index=True)
    q["Rank"] = q.index + 1
    q["GanaEscaño"] = q["Rank"] <= seats_
    alloc = pd.Series(0, index=df_.index, dtype=int)
    for _, rr in q[q["GanaEscaño"]].iterrows():
        alloc.loc[rr["idx"]] += 1
    return alloc, q

def color_for(name: str):
    h = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16)
    t = (h % 1000) / 1000.0
    return plt.cm.tab20(t % 1.0)

# ---------- sidebar ----------
with st.sidebar:
    seats = st.number_input("Escaños a repartir", min_value=1, max_value=200, value=30, step=1)
    order_chart = st.toggle("Ordenar gráfico por votos (desc.)", value=True)
    st.markdown("---")
    colA, colB, colC = st.columns(3)
    if colA.button("➕ Agregar fila"):
        st.session_state.rows.append(_mk_row("Nuevo partido", 0))
    if colB.button("➖ Quitar última"):
        if st.session_state.rows:
            st.session_state.rows.pop()
    if colC.button("↺ Restablecer"):
        st.session_state.rows = _init_rows_with_ids()

# ---------- formulario de edición (clave para Cloud) ----------
st.subheader("📋 Partidos y votos (usa “Aplicar cambios” para guardar)")
with st.form("editor", clear_on_submit=False):
    new_rows = []
    remove_ids = []
    for i, row in enumerate(st.session_state.rows):
        rid = row["id"]
        c1, c2, c3 = st.columns([3, 1, 0.6], gap="small")
        name = c1.text_input(f"Partido #{i+1}", value=row.get("Partido",""), key=f"name_{rid}")
        votes = c2.number_input("Votos", min_value=0, step=1, value=int(row.get("Votos",0)), key=f"votes_{rid}")
        rm = c3.checkbox("Quitar", value=False, key=f"rm_{rid}")
        if rm:
            remove_ids.append(rid)
        else:
            new_rows.append({"id": rid, "Partido": name, "Votos": int(votes)})

    submitted = st.form_submit_button("✅ Aplicar cambios")

# aplica cambios del form SOLO cuando se pulsa el botón
if submitted:
    st.session_state.rows = new_rows
    st.success("Cambios aplicados.")

# ---------- cálculos ----------
df = sanitize(pd.DataFrame(st.session_state.rows, columns=["id", *REQUIRED_COLS]).drop(columns=["id"]))
total_votes = int(df["Votos"].sum())
df["%"] = (df["Votos"] / max(total_votes,1) * 100).round(2)
alloc, qdf = dhondt(df, int(seats))
df["Escaños"] = alloc

# ---------- visualización ----------
c1, c2 = st.columns([2, 1], gap="large")

with c1:
    st.subheader("📊 Gráfico de votos (colores únicos por partido)")
    plot_df = df.sort_values(["Votos","Escaños","Partido"], ascending=[False, False, True]) if order_chart else df
    color_map = {p: color_for(p) for p in df["Partido"]}
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(plot_df["Partido"], plot_df["Votos"], color=[color_map[p] for p in plot_df["Partido"]])
    ax.set_xlabel("Partido"); ax.set_ylabel("Votos")
    ax.tick_params(axis="x", rotation=30)
    st.pyplot(fig, clear_figure=True)

with c2:
    st.subheader("ℹ️ Totales")
    st.metric("Total de votos", f"{total_votes:,}".replace(",", "."))
    winners = df[df["Escaños"] > 0][["Partido","Escaños"]].sort_values(["Escaños","Partido"], ascending=[False, True])
    if winners.empty:
        st.caption("(Sin asignaciones)")
    else:
        st.table(winners.set_index("Partido"))

st.subheader("📑 Tabla con porcentajes y escaños")
st.dataframe(
    df.sort_values("Votos", ascending=False).set_index("Partido")[["Votos","%","Escaños"]],
    use_container_width=True
)

# ---------- Matriz de cocientes 1..N con top-N resaltado ----------
st.subheader(f"🔍 Cocientes D’Hondt por partido (divisores 1..{seats})")

divisores = list(range(1, int(seats) + 1))
cols = [f"÷{d}" for d in divisores]
m = pd.DataFrame(index=df["Partido"], columns=cols, dtype=float)
for _, r in df.iterrows():
    for d in divisores:
        m.at[r["Partido"], f"÷{d}"] = r["Votos"] / d

m_int = m.round(0).astype(int)
flat = m.stack().sort_values(ascending=False).head(int(seats))  # ranking sin redondear
mask = pd.DataFrame(False, index=m.index, columns=m.columns)
for idx, col in flat.index:
    mask.loc[idx, col] = True

def highlight(row):
    ri = row.name
    return [
        "background-color: #1f6feb; color: white; font-weight: bold; border: 2px solid #0b4eda"
        if mask.loc[ri, col] else "" for col in row.index
    ]

try:
    st.write(m_int.style
             .apply(highlight, axis=1)
             .set_properties(**{"text-align":"center"})
             .set_table_styles([{"selector":"th","props":[("text-align","center"),("font-weight","bold")]}]))
except Exception:
    st.warning("Tu versión de pandas no soporta estilos; mostrando sin resaltado.")
    st.write(m_int)

# ---------- Descargas ----------
def to_csv_bytes(df_):
    s = io.StringIO(); df_[["Partido","Votos"]].to_csv(s, index=False); return s.getvalue().encode("utf-8")
def to_json_bytes(df_):
    s = io.StringIO(); df_[["Partido","Votos"]].to_json(s, orient="records", force_ascii=False); return s.getvalue().encode("utf-8")

st.download_button("⬇️ CSV (Partidos,Votos)", data=to_csv_bytes(df), file_name="partidos_votos.csv", mime="text/csv")
st.download_button("⬇️ JSON", data=to_json_bytes(df), file_name="partidos_votos.json", mime="application/json")
