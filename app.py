import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client, Client

# ─────────────────────────────────────────────
# SAYFA AYARLARI
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Pastane Yönetim",
    page_icon="🎂",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.stApp { background-color: #fdf8f4; }
[data-testid="stSidebar"] {
    background-color: #fff5f0;
    border-right: 1px solid #f0ddd6;
}
h1, h2, h3 { color: #5a2d2d; }
[data-testid="metric-container"] {
    background-color: #fff0eb;
    border: 1px solid #f0d5cb;
    border-radius: 12px;
    padding: 12px;
}
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
# SUPABASE BAĞLANTISI
# ─────────────────────────────────────────────
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()


# ─────────────────────────────────────────────
# VERİTABANI KATMANI
# ─────────────────────────────────────────────

def list_recipes() -> pd.DataFrame:
    res = supabase.table("recipes").select("*").order("created_at", desc=True).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def get_recipe(recipe_id: int) -> dict | None:
    res = supabase.table("recipes").select("*").eq("id", recipe_id).single().execute()
    return res.data

def add_recipe(name: str, servings: int, notes: str) -> int:
    res = supabase.table("recipes").insert({
        "name": name, "servings": servings, "notes": notes
    }).execute()
    return res.data[0]["id"]

def delete_recipe(recipe_id: int):
    supabase.table("recipes").delete().eq("id", recipe_id).execute()

def get_ingredients(recipe_id: int) -> pd.DataFrame:
    res = supabase.table("ingredients").select("*").eq("recipe_id", recipe_id).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def add_ingredient(recipe_id: int, name: str, qty: float, unit: str, price: float):
    supabase.table("ingredients").insert({
        "recipe_id": recipe_id, "name": name,
        "quantity": qty, "unit": unit, "unit_price": price,
    }).execute()

def delete_ingredient(ingredient_id: int):
    supabase.table("ingredients").delete().eq("id", ingredient_id).execute()

def list_orders() -> pd.DataFrame:
    res = supabase.table("orders").select("*, recipes(name)").order("delivery_date").execute()
    if not res.data:
        return pd.DataFrame()
    rows = []
    for o in res.data:
        recipe_name = o.get("recipes") or {}
        rows.append({
            "id": o["id"],
            "customer_name": o["customer_name"],
            "delivery_date": o["delivery_date"],
            "theme": o.get("theme", ""),
            "recipe_name": recipe_name.get("name", "-") if recipe_name else "-",
            "servings": o.get("servings", 1),
            "notes": o.get("notes", ""),
            "status": o.get("status", "Bekliyor"),
        })
    return pd.DataFrame(rows)

def add_order(customer, delivery, theme, recipe_id, servings, notes):
    supabase.table("orders").insert({
        "customer_name": customer, "delivery_date": delivery,
        "theme": theme, "recipe_id": recipe_id,
        "servings": servings, "notes": notes,
    }).execute()

def update_order_status(order_id: int, status: str):
    supabase.table("orders").update({"status": status}).eq("id", order_id).execute()

def delete_order(order_id: int):
    supabase.table("orders").delete().eq("id", order_id).execute()


# ─────────────────────────────────────────────
# HESAPLAMA MANTIĞI
# ─────────────────────────────────────────────

def calculate_cost(ingredients_df: pd.DataFrame, scale: float = 1.0) -> float:
    if ingredients_df.empty:
        return 0.0
    return round(float((ingredients_df["quantity"] * ingredients_df["unit_price"] * scale).sum()), 2)

def scale_ingredients(df: pd.DataFrame, scale: float) -> pd.DataFrame:
    scaled = df.copy()
    scaled["quantity"] = (scaled["quantity"] * scale).round(3)
    return scaled


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.markdown("## 🎂 Pastane")
        st.markdown("---")
        page = st.radio("Menü", ["📋 Reçete Defteri", "🛒 Sipariş Takibi", "📊 Özet"],
                        label_visibility="collapsed")
        st.markdown("---")
        st.caption("Veriler Supabase'de güvenle saklanır.")
    return page


# ─────────────────────────────────────────────
# REÇETE SAYFASI
# ─────────────────────────────────────────────

def page_recipes():
    st.title("📋 Reçete Defteri")
    tab_list, tab_new = st.tabs(["Reçeteler", "Yeni Reçete Ekle"])

    with tab_list:
        recipes_df = list_recipes()
        if recipes_df.empty:
            st.info("Henüz reçete eklenmemiş.")
            return

        recipe_names = dict(zip(recipes_df["id"], recipes_df["name"]))
        selected_id = st.selectbox("Reçete seçin", list(recipe_names.keys()),
                                   format_func=lambda x: recipe_names[x])
        recipe = get_recipe(selected_id)
        if not recipe:
            return

        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(recipe["name"])
            if recipe.get("notes"):
                st.caption(f"📝 {recipe['notes']}")
        with col2:
            if st.button("🗑️ Reçeteyi Sil"):
                delete_recipe(selected_id)
                st.success("Silindi.")
                st.rerun()

        base_servings = recipe["servings"]
        st.markdown('<p class="section-header">Dinamik Ölçeklendirme</p>', unsafe_allow_html=True)
        target_servings = st.slider(f"Kişi sayısı (orijinal: {base_servings})",
                                    1, max(200, base_servings * 10), base_servings)
        scale = target_servings / base_servings

        ing_df = get_ingredients(selected_id)
        st.markdown('<p class="section-header">Malzemeler</p>', unsafe_allow_html=True)

        if not ing_df.empty:
            display_df = scale_ingredients(ing_df, scale)
            display_df["Maliyet (₺)"] = (display_df["quantity"] * display_df["unit_price"]).round(2)
            show_df = display_df.rename(columns={
                "name": "Malzeme", "quantity": f"Miktar ({target_servings} kişi)",
                "unit": "Birim", "unit_price": "Birim Fiyat (₺)",
            })[["Malzeme", f"Miktar ({target_servings} kişi)", "Birim", "Birim Fiyat (₺)", "Maliyet (₺)"]]
            st.dataframe(show_df, use_container_width=True, hide_index=True)

            total = calculate_cost(ing_df, scale)
            per_person = round(total / target_servings, 2) if target_servings else 0
            m1, m2, m3 = st.columns(3)
            m1.metric("Toplam Maliyet", f"₺{total:,.2f}")
            m2.metric("Kişi Başı Maliyet", f"₺{per_person:,.2f}")
            m3.metric("Porsiyon Katsayısı", f"×{scale:.2f}")

            with st.expander("Malzeme sil"):
                ing_opts = dict(zip(ing_df["id"], ing_df["name"]))
                del_id = st.selectbox("Silinecek", list(ing_opts.keys()), format_func=lambda x: ing_opts[x])
                if st.button("Sil"):
                    delete_ingredient(del_id)
                    st.rerun()
        else:
            st.info("Bu reçetede henüz malzeme yok.")

        st.markdown('<p class="section-header">Malzeme Ekle</p>', unsafe_allow_html=True)
        with st.form("add_ing", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            ing_name = c1.text_input("Malzeme adı", placeholder="Un")
            ing_qty = c2.number_input("Miktar", min_value=0.0, step=0.1, value=100.0)
            ing_unit = c3.selectbox("Birim", ["g", "kg", "ml", "lt", "adet", "yemek k.", "çay k.", "su bardağı"])
            ing_price = c4.number_input("Birim Fiyat (₺)", min_value=0.0, step=0.1)
            if st.form_submit_button("➕ Ekle"):
                if ing_name.strip():
                    add_ingredient(selected_id, ing_name.strip(), ing_qty, ing_unit, ing_price)
                    st.success(f"'{ing_name}' eklendi.")
                    st.rerun()
                else:
                    st.warning("Malzeme adı boş olamaz.")

    with tab_new:
        with st.form("new_recipe", clear_on_submit=True):
            r_name = st.text_input("Reçete adı *", placeholder="Çikolatalı Tart")
            r_servings = st.number_input("Kaç kişilik?", min_value=1, value=8, step=1)
            r_notes = st.text_area("Notlar", placeholder="Glutensiz, Vegan vb.")
            if st.form_submit_button("✅ Kaydet"):
                if r_name.strip():
                    add_recipe(r_name.strip(), int(r_servings), r_notes)
                    st.success(f"'{r_name}' kaydedildi!")
                    st.rerun()
                else:
                    st.warning("Reçete adı zorunludur.")


# ─────────────────────────────────────────────
# SİPARİŞ SAYFASI
# ─────────────────────────────────────────────

def page_orders():
    st.title("🛒 Sipariş Takibi")
    tab_list, tab_new = st.tabs(["Siparişler", "Yeni Sipariş Ekle"])

    with tab_list:
        orders_df = list_orders()
        if orders_df.empty:
            st.info("Henüz sipariş yok.")
        else:
            status_filter = st.multiselect("Duruma göre filtrele",
                ["Bekliyor", "Hazırlanıyor", "Teslim Edildi", "İptal"],
                default=["Bekliyor", "Hazırlanıyor"])
            filtered = orders_df[orders_df["status"].isin(status_filter)] if status_filter else orders_df

            def status_color(val):
                return {
                    "Bekliyor": "background-color:#fff3cd;color:#7a5a00",
                    "Hazırlanıyor": "background-color:#d1ecf1;color:#0c5460",
                    "Teslim Edildi": "background-color:#d4edda;color:#155724",
                    "İptal": "background-color:#f8d7da;color:#721c24",
                }.get(val, "")

            show = filtered.rename(columns={
                "id": "ID", "customer_name": "Müşteri", "delivery_date": "Teslimat",
                "theme": "Tema", "recipe_name": "Reçete", "servings": "Kişi",
                "notes": "Notlar", "status": "Durum",
            })[["ID","Müşteri","Teslimat","Tema","Reçete","Kişi","Notlar","Durum"]]
            st.dataframe(show.style.applymap(status_color, subset=["Durum"]),
                         use_container_width=True, hide_index=True)

            with st.expander("Sipariş güncelle / sil"):
                oid = st.number_input("Sipariş ID", min_value=1, step=1)
                ca, cb = st.columns(2)
                with ca:
                    ns = st.selectbox("Yeni durum", ["Bekliyor", "Hazırlanıyor", "Teslim Edildi", "İptal"])
                    if st.button("Durumu Güncelle"):
                        update_order_status(int(oid), ns)
                        st.success("Güncellendi!")
                        st.rerun()
                with cb:
                    st.write("")
                    st.write("")
                    if st.button("🗑️ Siparişi Sil"):
                        delete_order(int(oid))
                        st.success("Silindi.")
                        st.rerun()

    with tab_new:
        recipes_df = list_recipes()
        recipe_options = {"(Reçetesiz)": None}
        if not recipes_df.empty:
            recipe_options.update(dict(zip(recipes_df["name"], recipes_df["id"])))

        with st.form("new_order", clear_on_submit=True):
            o_customer = st.text_input("Müşteri adı *", placeholder="Ayşe Hanım")
            o_delivery = st.date_input("Teslimat tarihi *", value=date.today())
            o_theme = st.text_input("Pasta teması", placeholder="Doğum günü, Düğün...")
            o_recipe = st.selectbox("Reçete (opsiyonel)", list(recipe_options.keys()))
            o_servings = st.number_input("Kişi sayısı", min_value=1, value=10, step=1)
            o_notes = st.text_area("Özel notlar / Alerjen uyarıları",
                                   placeholder="Fındık alerjisi var...")
            if st.form_submit_button("✅ Siparişi Kaydet"):
                if o_customer.strip():
                    add_order(o_customer.strip(), str(o_delivery), o_theme,
                              recipe_options[o_recipe], int(o_servings), o_notes)
                    st.success(f"'{o_customer}' için sipariş oluşturuldu!")
                    st.rerun()
                else:
                    st.warning("Müşteri adı zorunludur.")


# ─────────────────────────────────────────────
# ÖZET SAYFASI
# ─────────────────────────────────────────────

def page_summary():
    st.title("📊 Özet")
    orders_df = list_orders()
    recipes_df = list_recipes()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Reçete", len(recipes_df))
    c2.metric("Toplam Sipariş", len(orders_df))

    if not orders_df.empty:
        c3.metric("Bekliyor", len(orders_df[orders_df["status"] == "Bekliyor"]))
        c4.metric("Hazırlanıyor", len(orders_df[orders_df["status"] == "Hazırlanıyor"]))

        st.markdown("---")
        st.subheader("Yaklaşan Teslimatlar (7 gün)")
        today_str = date.today().isoformat()
        week_later = date.fromordinal(date.today().toordinal() + 7).isoformat()
        upcoming = orders_df[
            (orders_df["delivery_date"] >= today_str) &
            (orders_df["delivery_date"] <= week_later) &
            (orders_df["status"].isin(["Bekliyor", "Hazırlanıyor"]))
        ]
        if upcoming.empty:
            st.info("Önümüzdeki 7 günde teslimat yok.")
        else:
            u = upcoming[["customer_name","delivery_date","theme","servings","status","notes"]].copy()
            u.columns = ["Müşteri","Teslimat","Tema","Kişi","Durum","Notlar"]
            st.dataframe(u, use_container_width=True, hide_index=True)

        st.subheader("Sipariş Durumu Dağılımı")
        sc = orders_df["status"].value_counts().reset_index()
        sc.columns = ["Durum", "Adet"]
        st.bar_chart(sc.set_index("Durum"))
    else:
        c3.metric("Bekliyor", 0)
        c4.metric("Hazırlanıyor", 0)
        st.info("Henüz sipariş verisi yok.")


# ─────────────────────────────────────────────
# ANA GİRİŞ NOKTASI
# ─────────────────────────────────────────────

def main():
    page = render_sidebar()
    if page == "📋 Reçete Defteri":
        page_recipes()
    elif page == "🛒 Sipariş Takibi":
        page_orders()
    elif page == "📊 Özet":
        page_summary()

if __name__ == "__main__":
    main()
