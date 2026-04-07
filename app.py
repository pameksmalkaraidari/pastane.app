import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime

# ─────────────────────────────────────────────
# SAYFA AYARLARI
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Pastane Yönetim",
    page_icon="🎂",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# TEMA / STİL
# ─────────────────────────────────────────────
st.markdown("""
<style>
/* Genel arka plan */
.stApp { background-color: #fdf8f4; }

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #fff5f0;
    border-right: 1px solid #f0ddd6;
}

/* Başlık rengi */
h1, h2, h3 { color: #5a2d2d; }

/* Metric kartları */
[data-testid="metric-container"] {
    background-color: #fff0eb;
    border: 1px solid #f0d5cb;
    border-radius: 12px;
    padding: 12px;
}

/* Butonlar */
.stButton > button {
    background-color: #c97b5a;
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 500;
    padding: 0.4rem 1.2rem;
}
.stButton > button:hover {
    background-color: #a85e3f;
    color: white;
}

/* Başarı mesajı */
.stSuccess { border-radius: 8px; }

/* Form alanları */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div {
    border-radius: 8px;
    border-color: #e8cfc5;
}

/* Tablo */
.dataframe { font-size: 13px; }

/* Alt çizgi başlıkları */
.section-header {
    font-size: 1.1rem;
    font-weight: 600;
    color: #7a3d2d;
    border-bottom: 2px solid #f0d5cb;
    padding-bottom: 6px;
    margin-bottom: 16px;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# VERİTABANI KATMANI
# ─────────────────────────────────────────────
DB_PATH = "pastane.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Tablolar yoksa oluştur."""
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS recipes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            servings    INTEGER NOT NULL DEFAULT 1,
            notes       TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS ingredients (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id   INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            quantity    REAL NOT NULL,
            unit        TEXT NOT NULL,
            unit_price  REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name   TEXT NOT NULL,
            delivery_date   TEXT NOT NULL,
            theme           TEXT,
            recipe_id       INTEGER REFERENCES recipes(id),
            servings        INTEGER DEFAULT 1,
            notes           TEXT,
            status          TEXT DEFAULT 'Bekliyor',
            created_at      TEXT DEFAULT (datetime('now','localtime'))
        );
        """)


# ── Reçete CRUD ──────────────────────────────

def list_recipes() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql("SELECT * FROM recipes ORDER BY created_at DESC", conn)


def get_recipe(recipe_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM recipes WHERE id=?", (recipe_id,)).fetchone()


def add_recipe(name: str, servings: int, notes: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO recipes (name, servings, notes) VALUES (?,?,?)",
            (name, servings, notes),
        )
        return cur.lastrowid


def delete_recipe(recipe_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM recipes WHERE id=?", (recipe_id,))


# ── Malzeme CRUD ─────────────────────────────

def get_ingredients(recipe_id: int) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql(
            "SELECT * FROM ingredients WHERE recipe_id=? ORDER BY id",
            conn, params=(recipe_id,),
        )


def add_ingredient(recipe_id: int, name: str, qty: float, unit: str, price: float):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO ingredients (recipe_id, name, quantity, unit, unit_price) VALUES (?,?,?,?,?)",
            (recipe_id, name, qty, unit, price),
        )


def delete_ingredient(ingredient_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM ingredients WHERE id=?", (ingredient_id,))


# ── Sipariş CRUD ─────────────────────────────

def list_orders() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql("""
            SELECT o.id, o.customer_name, o.delivery_date, o.theme,
                   r.name as recipe_name, o.servings,
                   o.notes, o.status, o.created_at
            FROM orders o
            LEFT JOIN recipes r ON r.id = o.recipe_id
            ORDER BY o.delivery_date
        """, conn)


def add_order(customer: str, delivery: str, theme: str,
              recipe_id: int | None, servings: int, notes: str):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO orders
               (customer_name, delivery_date, theme, recipe_id, servings, notes)
               VALUES (?,?,?,?,?,?)""",
            (customer, delivery, theme, recipe_id or None, servings, notes),
        )


def update_order_status(order_id: int, status: str):
    with get_connection() as conn:
        conn.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))


def delete_order(order_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM orders WHERE id=?", (order_id,))


# ─────────────────────────────────────────────
# HESAPLAMA MANTIĞI
# ─────────────────────────────────────────────

def calculate_cost(ingredients_df: pd.DataFrame, scale: float = 1.0) -> float:
    """Malzeme maliyetini hesapla, scale=hedef_porsiyon/orijinal_porsiyon."""
    if ingredients_df.empty:
        return 0.0
    total = (ingredients_df["quantity"] * ingredients_df["unit_price"] * scale).sum()
    return round(float(total), 2)


def scale_ingredients(df: pd.DataFrame, scale: float) -> pd.DataFrame:
    """Malzeme miktarlarını ölçekle (orijinali değiştirmez)."""
    scaled = df.copy()
    scaled["quantity"] = (scaled["quantity"] * scale).round(3)
    return scaled


# ─────────────────────────────────────────────
# UI BİLEŞENLERİ
# ─────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.markdown("## 🎂 Pastane")
        st.markdown("---")
        page = st.radio(
            "Menü",
            ["📋 Reçete Defteri", "🛒 Sipariş Takibi", "📊 Özet"],
            label_visibility="collapsed",
        )
        st.markdown("---")
        st.caption("Veri yerel SQLite'da saklanır.")
    return page


# ── REÇETE SAYFASI ───────────────────────────

def page_recipes():
    st.title("📋 Reçete Defteri")

    tab_list, tab_new = st.tabs(["Reçeteler", "Yeni Reçete Ekle"])

    # ─ Mevcut reçeteler ─
    with tab_list:
        recipes_df = list_recipes()
        if recipes_df.empty:
            st.info("Henüz reçete eklenmemiş. 'Yeni Reçete Ekle' sekmesini kullanın.")
            return

        recipe_names = dict(zip(recipes_df["id"], recipes_df["name"]))
        selected_id = st.selectbox(
            "Reçete seçin",
            options=list(recipe_names.keys()),
            format_func=lambda x: recipe_names[x],
        )

        recipe = get_recipe(selected_id)
        if not recipe:
            return

        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(recipe["name"])
            if recipe["notes"]:
                st.caption(f"📝 {recipe['notes']}")
        with col2:
            if st.button("🗑️ Reçeteyi Sil", key="del_recipe"):
                delete_recipe(selected_id)
                st.success("Reçete silindi.")
                st.rerun()

        # Ölçeklendirme
        base_servings = recipe["servings"]
        st.markdown('<p class="section-header">Dinamik Ölçeklendirme</p>', unsafe_allow_html=True)
        target_servings = st.slider(
            f"Kişi sayısı (orijinal: {base_servings})",
            min_value=1,
            max_value=max(200, base_servings * 10),
            value=base_servings,
            step=1,
        )
        scale = target_servings / base_servings

        # Malzeme tablosu
        ing_df = get_ingredients(selected_id)
        st.markdown('<p class="section-header">Malzemeler</p>', unsafe_allow_html=True)

        if not ing_df.empty:
            display_df = scale_ingredients(ing_df, scale)
            display_df["Maliyet (₺)"] = (
                display_df["quantity"] * display_df["unit_price"]
            ).round(2)
            show_cols = {
                "name": "Malzeme",
                "quantity": f"Miktar ({target_servings} kişi)",
                "unit": "Birim",
                "unit_price": "Birim Fiyat (₺)",
                "Maliyet (₺)": "Maliyet (₺)",
            }
            show_df = display_df.rename(columns=show_cols)[list(show_cols.values())]
            st.dataframe(show_df, use_container_width=True, hide_index=True)

            total = calculate_cost(ing_df, scale)
            per_person = round(total / target_servings, 2) if target_servings else 0

            m1, m2, m3 = st.columns(3)
            m1.metric("Toplam Maliyet", f"₺{total:,.2f}")
            m2.metric("Kişi Başı Maliyet", f"₺{per_person:,.2f}")
            m3.metric("Porsiyon Katsayısı", f"×{scale:.2f}")

            # Malzeme sil
            with st.expander("Malzeme sil"):
                ing_options = dict(zip(ing_df["id"], ing_df["name"]))
                del_id = st.selectbox("Silinecek malzeme", options=list(ing_options.keys()),
                                      format_func=lambda x: ing_options[x])
                if st.button("Sil"):
                    delete_ingredient(del_id)
                    st.rerun()
        else:
            st.info("Bu reçetede henüz malzeme yok.")

        # Malzeme ekle
        st.markdown('<p class="section-header">Malzeme Ekle</p>', unsafe_allow_html=True)
        with st.form("add_ingredient_form", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            ing_name = c1.text_input("Malzeme adı", placeholder="Un")
            ing_qty = c2.number_input("Miktar", min_value=0.0, step=0.1, value=100.0)
            ing_unit = c3.selectbox("Birim", ["g", "kg", "ml", "lt", "adet", "yemek k.", "çay k.", "su bardağı"])
            ing_price = c4.number_input("Birim Fiyat (₺)", min_value=0.0, step=0.1, value=0.0)
            if st.form_submit_button("➕ Ekle"):
                if ing_name.strip():
                    add_ingredient(selected_id, ing_name.strip(), ing_qty, ing_unit, ing_price)
                    st.success(f"'{ing_name}' eklendi.")
                    st.rerun()
                else:
                    st.warning("Malzeme adı boş olamaz.")

    # ─ Yeni reçete ─
    with tab_new:
        st.markdown('<p class="section-header">Yeni Reçete</p>', unsafe_allow_html=True)
        with st.form("new_recipe_form", clear_on_submit=True):
            r_name = st.text_input("Reçete adı *", placeholder="Çikolatalı Tart")
            r_servings = st.number_input("Kaç kişilik?", min_value=1, value=8, step=1)
            r_notes = st.text_area("Notlar / Açıklama", placeholder="Glutensiz, Vegan vb.")
            submitted = st.form_submit_button("✅ Reçeteyi Kaydet")
            if submitted:
                if r_name.strip():
                    new_id = add_recipe(r_name.strip(), int(r_servings), r_notes)
                    st.success(f"'{r_name}' kaydedildi! (ID: {new_id})")
                    st.rerun()
                else:
                    st.warning("Reçete adı zorunludur.")


# ── SİPARİŞ SAYFASI ──────────────────────────

def page_orders():
    st.title("🛒 Sipariş Takibi")

    tab_list, tab_new = st.tabs(["Siparişler", "Yeni Sipariş Ekle"])

    with tab_list:
        orders_df = list_orders()
        if orders_df.empty:
            st.info("Henüz sipariş yok.")
        else:
            # Durum filtresi
            status_filter = st.multiselect(
                "Duruma göre filtrele",
                ["Bekliyor", "Hazırlanıyor", "Teslim Edildi", "İptal"],
                default=["Bekliyor", "Hazırlanıyor"],
            )
            filtered = orders_df[orders_df["status"].isin(status_filter)] if status_filter else orders_df

            # Durum rengi
            def status_color(val):
                colors = {
                    "Bekliyor": "background-color: #fff3cd; color: #7a5a00",
                    "Hazırlanıyor": "background-color: #d1ecf1; color: #0c5460",
                    "Teslim Edildi": "background-color: #d4edda; color: #155724",
                    "İptal": "background-color: #f8d7da; color: #721c24",
                }
                return colors.get(val, "")

            display_cols = {
                "id": "ID",
                "customer_name": "Müşteri",
                "delivery_date": "Teslimat",
                "theme": "Tema",
                "recipe_name": "Reçete",
                "servings": "Kişi",
                "notes": "Notlar",
                "status": "Durum",
            }
            show = filtered.rename(columns=display_cols)[list(display_cols.values())]
            st.dataframe(
                show.style.applymap(status_color, subset=["Durum"]),
                use_container_width=True,
                hide_index=True,
            )

            # Durum güncelle / sil
            with st.expander("Sipariş güncelle / sil"):
                order_id_input = st.number_input("Sipariş ID", min_value=1, step=1)
                col_a, col_b = st.columns(2)
                with col_a:
                    new_status = st.selectbox("Yeni durum", ["Bekliyor", "Hazırlanıyor", "Teslim Edildi", "İptal"])
                    if st.button("Durumu Güncelle"):
                        update_order_status(int(order_id_input), new_status)
                        st.success("Güncellendi!")
                        st.rerun()
                with col_b:
                    st.write("")
                    st.write("")
                    if st.button("🗑️ Siparişi Sil"):
                        delete_order(int(order_id_input))
                        st.success("Sipariş silindi.")
                        st.rerun()

    with tab_new:
        st.markdown('<p class="section-header">Yeni Sipariş</p>', unsafe_allow_html=True)
        recipes_df = list_recipes()
        recipe_options = {"(Reçetesiz)": None}
        recipe_options.update(dict(zip(recipes_df["name"], recipes_df["id"])) if not recipes_df.empty else {})

        with st.form("new_order_form", clear_on_submit=True):
            o_customer = st.text_input("Müşteri adı *", placeholder="Ayşe Hanım")
            o_delivery = st.date_input("Teslimat tarihi *", value=date.today())
            o_theme = st.text_input("Pasta teması", placeholder="Doğum günü, Düğün...")
            o_recipe_name = st.selectbox("Reçete (opsiyonel)", list(recipe_options.keys()))
            o_servings = st.number_input("Kişi sayısı", min_value=1, value=10, step=1)
            o_notes = st.text_area("Özel notlar / Alerjen uyarıları",
                                   placeholder="Fındık alerjisi var, şeker az kullanılsın...")
            if st.form_submit_button("✅ Siparişi Kaydet"):
                if o_customer.strip():
                    recipe_id = recipe_options[o_recipe_name]
                    add_order(
                        o_customer.strip(),
                        str(o_delivery),
                        o_theme,
                        recipe_id,
                        int(o_servings),
                        o_notes,
                    )
                    st.success(f"'{o_customer}' için sipariş oluşturuldu!")
                    st.rerun()
                else:
                    st.warning("Müşteri adı zorunludur.")


# ── ÖZET SAYFASI ─────────────────────────────

def page_summary():
    st.title("📊 Özet")

    orders_df = list_orders()
    recipes_df = list_recipes()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Reçete", len(recipes_df))
    c2.metric("Toplam Sipariş", len(orders_df))

    if not orders_df.empty:
        pending = len(orders_df[orders_df["status"] == "Bekliyor"])
        in_progress = len(orders_df[orders_df["status"] == "Hazırlanıyor"])
        c3.metric("Bekliyor", pending)
        c4.metric("Hazırlanıyor", in_progress)

        st.markdown("---")
        st.subheader("Yaklaşan Teslimatlar (7 gün)")
        today_str = date.today().isoformat()
        week_later = (date.today().replace(day=date.today().day + 7)).isoformat()
        upcoming = orders_df[
            (orders_df["delivery_date"] >= today_str) &
            (orders_df["delivery_date"] <= week_later) &
            (orders_df["status"].isin(["Bekliyor", "Hazırlanıyor"]))
        ].copy()

        if upcoming.empty:
            st.info("Önümüzdeki 7 günde teslimat yok.")
        else:
            upcoming_show = upcoming[["customer_name", "delivery_date", "theme", "servings", "status", "notes"]]
            upcoming_show.columns = ["Müşteri", "Teslimat", "Tema", "Kişi", "Durum", "Notlar"]
            st.dataframe(upcoming_show, use_container_width=True, hide_index=True)

        st.subheader("Sipariş Durumu Dağılımı")
        status_counts = orders_df["status"].value_counts().reset_index()
        status_counts.columns = ["Durum", "Adet"]
        st.bar_chart(status_counts.set_index("Durum"))
    else:
        c3.metric("Bekliyor", 0)
        c4.metric("Hazırlanıyor", 0)
        st.info("Sipariş verisi bulunmuyor.")


# ─────────────────────────────────────────────
# ANA GİRİŞ NOKTASI
# ─────────────────────────────────────────────

def main():
    init_db()
    page = render_sidebar()

    if page == "📋 Reçete Defteri":
        page_recipes()
    elif page == "🛒 Sipariş Takibi":
        page_orders()
    elif page == "📊 Özet":
        page_summary()


if __name__ == "__main__":
    main()
