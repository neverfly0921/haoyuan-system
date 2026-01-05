import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import os

# --- 1. 資料庫初始化 ---
def init_db():
    conn = sqlite3.connect('haoyuan.db')
    c = conn.cursor()
    # 廠商基礎表（系統設定只管理廠商）
    c.execute('CREATE TABLE IF NOT EXISTS base_options (type TEXT, value TEXT, PRIMARY KEY(type, value))')
    # 老闆娘匯款紀錄表
    c.execute('''CREATE TABLE IF NOT EXISTS remits 
                 (r_id INTEGER PRIMARY KEY AUTOINCREMENT, r_date TEXT, vendor TEXT, 
                  total_amount REAL, note TEXT)''')
    # 匯款項目表（不同車種不同單價）
    c.execute('''CREATE TABLE IF NOT EXISTS remit_items 
                 (item_id INTEGER PRIMARY KEY AUTOINCREMENT, r_id INTEGER, model TEXT, unit_price REAL, quantity INTEGER,
                  FOREIGN KEY(r_id) REFERENCES remits(r_id))''')
    # 庫存零件
    c.execute('CREATE TABLE IF NOT EXISTS inventory (part_id TEXT PRIMARY KEY, part_name TEXT, cost REAL, stock INTEGER)')
    # 車輛主表
    c.execute('''CREATE TABLE IF NOT EXISTS vehicle_master 
                 (vin TEXT PRIMARY KEY, engine TEXT, v_type TEXT, vendor TEXT, brand TEXT, model TEXT, 
                  year TEXT, color TEXT, cost REAL, inv_in TEXT, remit_id INTEGER,
                  cust_name TEXT, cust_phone TEXT, cust_birthday TEXT, cust_address TEXT,
                  out_date TEXT, plate_no TEXT, inv_out TEXT, 
                  finance_subsidy REAL, acc_credit REAL, profit REAL, status TEXT, sales_person TEXT)''')
    
    # 添加缺失的欄位（兼容舊資料庫）
    columns_to_add = [
        ('v_type', 'TEXT'),
        ('vendor', 'TEXT'),
        ('color', 'TEXT'),
        ('cust_birthday', 'TEXT'),
        ('cust_address', 'TEXT'),
        ('finance_subsidy', 'REAL'),
        ('acc_credit', 'REAL'),
        ('sales_person', 'TEXT'),
        ('file_license', 'TEXT'),
        ('file_invoice', 'TEXT'),
        ('file_registration', 'TEXT'),
        ('file_original', 'TEXT'),
    ]
    c.execute('PRAGMA table_info(vehicle_master)')
    existing_columns = [col[1] for col in c.fetchall()]
    for col_name, col_type in columns_to_add:
        if col_name not in existing_columns:
            try:
                c.execute(f'ALTER TABLE vehicle_master ADD COLUMN {col_name} {col_type}')
            except:
                pass
    
    conn.commit()
    conn.close()

init_db()

# --- 2. 工具函數 ---
def get_vendors():
    """獲取廠商列表（只從系統設定）"""
    conn = sqlite3.connect('haoyuan.db')
    df = pd.read_sql_query("SELECT value FROM base_options WHERE type='廠商'", conn)
    conn.close()
    return df['value'].tolist() if not df.empty else []

def get_sales_persons():
    """獲取業務人員列表（從系統設定）"""
    conn = sqlite3.connect('haoyuan.db')
    df = pd.read_sql_query("SELECT value FROM base_options WHERE type='業務'", conn)
    conn.close()
    return df['value'].tolist() if not df.empty else []

def get_historical_options(column_name):
    """從車輛主表獲取歷史選項（年份/車款/顏色）"""
    conn = sqlite3.connect('haoyuan.db')
    try:
        df = pd.read_sql_query(f"SELECT DISTINCT {column_name} FROM vehicle_master WHERE {column_name} IS NOT NULL AND {column_name} != ''", conn)
        conn.close()
        return sorted(df[column_name].dropna().unique().tolist())
    except:
        conn.close()
        return []

# --- 3. 頁面導覽（營運數據分析設為首頁）---
st.set_page_config(page_title="豪元營運系統 7.0", layout="wide")
menu = st.sidebar.selectbox("模組切換", ["📊 營運數據分析", "💰 老闆娘匯款中心", "📥 新車進貨入庫", "🤝 業務銷售專區", "⚙️ 系統設定"])

# --- 4. 模組：營運數據分析（首頁）---
if menu == "📊 營運數據分析":
    st.header("📊 豪元營運分析看板")
    conn = sqlite3.connect('haoyuan.db')
    try:
        df = pd.read_sql_query("SELECT * FROM vehicle_master WHERE status='已售'", conn)
    except:
        df = pd.DataFrame()
    conn.close()

    if not df.empty:
        # 篩選器
        c1, c2 = st.columns(2)
        available_types = df['v_type'].dropna().unique().tolist() if 'v_type' in df.columns else []
        s_type = c1.multiselect("車輛來源篩選", available_types if available_types else ["公司車", "貿易車", "中古車"], 
                               default=available_types if available_types else ["公司車", "貿易車", "中古車"])
        # 日期篩選 (領牌區間)
        start_d = c2.date_input("開始日期", value=datetime(2024, 1, 1))
        end_d = c2.date_input("結束日期", value=datetime.now())
        
        # 應用篩選
        df_filtered = df.copy()
        if 'v_type' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['v_type'].isin(s_type)]
        if 'out_date' in df_filtered.columns:
            df_filtered = df_filtered[
                (df_filtered['out_date'].notna()) & 
                (df_filtered['out_date'] >= start_d.strftime("%Y-%m-%d")) & 
                (df_filtered['out_date'] <= end_d.strftime("%Y-%m-%d"))
            ]

        col1, col2, col3 = st.columns(3)
        col1.metric("總銷售台數", len(df_filtered))
        if 'profit' in df_filtered.columns:
            col2.metric("總銷售獲利", f"NT$ {df_filtered['profit'].sum():,.0f}")
            avg_profit = df_filtered['profit'].mean() if not df_filtered.empty else 0
            col3.metric("平均獲利", f"NT$ {avg_profit:,.0f}")
        
        # 業務人員篩選（在日期篩選之前）
        if 'sales_person' in df.columns and not df.empty:
            available_sales = sorted(df['sales_person'].dropna().unique().tolist())
            if available_sales:
                selected_sales = c1.multiselect("業務人員篩選", available_sales, default=available_sales)
                df_filtered = df_filtered[df_filtered['sales_person'].isin(selected_sales)]
        
        if 'sales_person' in df_filtered.columns and 'profit' in df_filtered.columns and not df_filtered.empty:
            st.subheader("業務銷售獲利統計")
            profit_by_name = df_filtered.groupby('sales_person')['profit'].sum().sort_values(ascending=False)
            st.bar_chart(profit_by_name)
        
        st.subheader("詳細銷售資料")
        st.dataframe(df_filtered, use_container_width=True)
    else:
        st.warning("尚無銷售數據。")

# --- 5. 模組：老闆娘匯款中心 ---
elif menu == "💰 老闆娘匯款中心":
    tab1, tab2, tab3 = st.tabs(["💰 建立匯款單", "📋 匯款清單與車輛對應", "🚗 所有車輛匯款清單"])
    
    with tab1:
        st.header("💰 老闆娘匯款管理 (資金來源)")
        
        # 初始化 session state
        if 'remit_items' not in st.session_state:
            st.session_state.remit_items = [{'model': '', 'unit_price': 0.0, 'quantity': 0}]
        
        # 動態項目管理（表單外）
        st.subheader("不同車種單價設定")
        col_btn1, col_btn2 = st.columns([1, 10])
        with col_btn1:
            if st.button("➕ 新增車種項目"):
                st.session_state.remit_items.append({'model': '', 'unit_price': 0.0, 'quantity': 0})
                st.rerun()
        
        # 顯示並管理項目列表（表單外）
        items_to_remove = []
        for i, item in enumerate(st.session_state.remit_items):
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            with col1:
                st.session_state.remit_items[i]['model'] = st.text_input(f"車款", value=item['model'], key=f"model_{i}")
            with col2:
                st.session_state.remit_items[i]['unit_price'] = st.number_input(f"單價", min_value=0.0, value=item['unit_price'], key=f"price_{i}")
            with col3:
                st.session_state.remit_items[i]['quantity'] = st.number_input(f"數量", min_value=0, value=item['quantity'], key=f"qty_{i}")
            with col4:
                if st.button("🗑️ 刪除", key=f"del_{i}"):
                    items_to_remove.append(i)
        
        # 移除標記的項目
        for i in reversed(items_to_remove):
            st.session_state.remit_items.pop(i)
            st.rerun()
        
        # 計算總金額
        total_amount = sum(item['unit_price'] * item['quantity'] for item in st.session_state.remit_items if item['model'])
        st.metric("總匯款金額", f"NT$ {total_amount:,.0f}")
        
        st.write("---")
        # 匯款單基本資訊（表單內）
        with st.form("remit_form"):
            vendor_opts = get_vendors()
            if not vendor_opts:
                st.warning("請先到「系統設定」新增廠商選項")
                r_vendor = None
            else:
                r_vendor = st.selectbox("匯款廠商", vendor_opts)
            r_date = st.date_input("匯款日期")
            r_note = st.text_area("匯款批次備註")
            
            if st.form_submit_button("儲存匯款單"):
                if r_vendor and total_amount > 0:
                    conn = sqlite3.connect('haoyuan.db')
                    c = conn.cursor()
                    # 插入匯款主表
                    c.execute("INSERT INTO remits (r_date, vendor, total_amount, note) VALUES (?, ?, ?, ?)",
                             (r_date.strftime("%Y-%m-%d"), r_vendor, total_amount, r_note))
                    r_id = c.lastrowid
                    # 插入匯款項目
                    for item in st.session_state.remit_items:
                        if item['model']:
                            c.execute("INSERT INTO remit_items (r_id, model, unit_price, quantity) VALUES (?, ?, ?, ?)",
                                     (r_id, item['model'], item['unit_price'], item['quantity']))
                    conn.commit()
                    conn.close()
                    # 清空 session state
                    st.session_state.remit_items = [{'model': '', 'unit_price': 0.0, 'quantity': 0}]
                    st.success("匯款單已建立")
                    st.rerun()
                else:
                    st.error("請填寫完整資訊且總金額需大於0")
    
    with tab2:
        st.header("📋 匯款清單與車輛對應")
        conn = sqlite3.connect('haoyuan.db')
        # 取得所有匯款記錄
        df_remits = pd.read_sql_query("SELECT * FROM remits ORDER BY r_date DESC", conn)
        
        if not df_remits.empty:
            for _, remit in df_remits.iterrows():
                with st.expander(f"匯款單 #{remit['r_id']} - {remit['vendor']} ({remit['r_date']}) - 總額: NT$ {remit['total_amount']:,.0f}"):
                    # 取得該匯款的項目
                    df_items = pd.read_sql_query("SELECT * FROM remit_items WHERE r_id=?", conn, params=(remit['r_id'],))
                    st.write("**匯款項目：**")
                    st.dataframe(df_items, use_container_width=True)
                    
                    # 取得該匯款下的車輛（已入庫）
                    df_vehicles = pd.read_sql_query("SELECT vin, engine, model, year, color, cost, profit, status FROM vehicle_master WHERE remit_id=?", 
                                                   conn, params=(remit['r_id'],))
                    
                    st.write("**已入庫車輛：**")
                    if not df_vehicles.empty:
                        st.dataframe(df_vehicles, use_container_width=True)
                        st.write(f"已入庫：{len(df_vehicles)} 台")
                        
                        # 修改/刪除功能
                        st.write("---")
                        st.subheader("修改/刪除車輛")
                        edit_vin = st.selectbox("選擇要修改或刪除的車輛", df_vehicles['vin'].tolist(), key=f"edit_vin_{remit['r_id']}")
                        
                        col_edit1, col_edit2 = st.columns(2)
                        with col_edit1:
                            if st.button("修改車輛資訊", key=f"edit_btn_{remit['r_id']}"):
                                st.session_state[f"edit_mode_{remit['r_id']}"] = edit_vin
                                st.rerun()
                        
                        with col_edit2:
                            if st.button("🗑️ 刪除車輛", key=f"del_btn_{remit['r_id']}"):
                                c = conn.cursor()
                                c.execute("UPDATE vehicle_master SET remit_id = NULL WHERE vin = ?", (edit_vin,))
                                conn.commit()
                                st.success(f"車輛 {edit_vin} 已從此匯款單移除")
                                st.rerun()
                        
                        # 編輯表單
                        if f"edit_mode_{remit['r_id']}" in st.session_state and st.session_state[f"edit_mode_{remit['r_id']}"]:
                            edit_vehicle = df_vehicles[df_vehicles['vin'] == st.session_state[f"edit_mode_{remit['r_id']}"]].iloc[0]
                            with st.form(f"edit_form_{remit['r_id']}"):
                                st.write("**修改車輛資訊：**")
                                edit_engine = st.text_input("引擎號碼", value=edit_vehicle.get('engine', ''))
                                edit_model = st.text_input("車款", value=edit_vehicle.get('model', ''))
                                profit_value = edit_vehicle.get('profit')
                                edit_profit = st.number_input("獲利", value=float(profit_value) if profit_value is not None else 0.0)
                                
                                col_submit1, col_submit2 = st.columns(2)
                                with col_submit1:
                                    if st.form_submit_button("💾 儲存修改"):
                                        c = conn.cursor()
                                        c.execute("UPDATE vehicle_master SET engine=?, model=?, profit=? WHERE vin=?", 
                                                (edit_engine, edit_model, edit_profit, st.session_state[f"edit_mode_{remit['r_id']}"]))
                                        conn.commit()
                                        st.success("修改完成")
                                        del st.session_state[f"edit_mode_{remit['r_id']}"]
                                        st.rerun()
                                with col_submit2:
                                    if st.form_submit_button("❌ 取消"):
                                        del st.session_state[f"edit_mode_{remit['r_id']}"]
                                        st.rerun()
                    else:
                        st.info("尚無已入庫車輛")
                    
                    # 計算未入庫數量
                    total_expected = df_items['quantity'].sum() if not df_items.empty else 0
                    total_in_stock = len(df_vehicles) if not df_vehicles.empty else 0
                    pending = total_expected - total_in_stock
                    st.write(f"**未入庫：** {pending} 台（預計 {total_expected} 台，已入庫 {total_in_stock} 台）")
                    
                    # 修改/刪除匯款單功能
                    st.write("---")
                    st.subheader("匯款單管理")
                    col_remit1, col_remit2 = st.columns(2)
                    with col_remit1:
                        if st.button("✏️ 修改匯款單", key=f"edit_remit_{remit['r_id']}"):
                            st.session_state[f"edit_remit_mode_{remit['r_id']}"] = True
                            st.rerun()
                    with col_remit2:
                        if st.button("🗑️ 刪除匯款單", key=f"del_remit_{remit['r_id']}"):
                            c = conn.cursor()
                            # 先將所有車輛的 remit_id 設為 NULL
                            c.execute("UPDATE vehicle_master SET remit_id = NULL WHERE remit_id = ?", (remit['r_id'],))
                            # 刪除匯款項目
                            c.execute("DELETE FROM remit_items WHERE r_id = ?", (remit['r_id'],))
                            # 刪除匯款單
                            c.execute("DELETE FROM remits WHERE r_id = ?", (remit['r_id'],))
                            conn.commit()
                            st.success(f"匯款單 #{remit['r_id']} 已刪除")
                            st.rerun()
                    
                    # 編輯匯款單表單
                    if f"edit_remit_mode_{remit['r_id']}" in st.session_state and st.session_state[f"edit_remit_mode_{remit['r_id']}"]:
                        with st.form(f"edit_remit_form_{remit['r_id']}"):
                            st.write("**修改匯款單資訊：**")
                            edit_vendor_opts = get_vendors()
                            edit_vendor = st.selectbox("廠商", edit_vendor_opts if edit_vendor_opts else [remit['vendor']], 
                                                      index=edit_vendor_opts.index(remit['vendor']) if remit['vendor'] in edit_vendor_opts else 0)
                            edit_date = st.date_input("匯款日期", value=datetime.strptime(remit['r_date'], "%Y-%m-%d").date())
                            edit_amount = st.number_input("總金額", value=float(remit['total_amount']))
                            edit_note = st.text_area("備註", value=remit.get('note', ''))
                            
                            col_submit1, col_submit2 = st.columns(2)
                            with col_submit1:
                                if st.form_submit_button("💾 儲存修改"):
                                    c = conn.cursor()
                                    c.execute("UPDATE remits SET vendor=?, r_date=?, total_amount=?, note=? WHERE r_id=?", 
                                            (edit_vendor, edit_date.strftime("%Y-%m-%d"), edit_amount, edit_note, remit['r_id']))
                                    conn.commit()
                                    st.success("匯款單修改完成")
                                    del st.session_state[f"edit_remit_mode_{remit['r_id']}"]
                                    st.rerun()
                            with col_submit2:
                                if st.form_submit_button("❌ 取消"):
                                    del st.session_state[f"edit_remit_mode_{remit['r_id']}"]
                                    st.rerun()
                    
                    # 帶入車輛功能
                    st.write("---")
                    st.subheader("帶入車輛到匯款單")
                    df_pending = pd.read_sql_query("SELECT vin, model, year, color FROM vehicle_master WHERE status='待售' AND (remit_id IS NULL OR remit_id = '')", conn)
                    if not df_pending.empty:
                        selected_vins = st.multiselect("選擇待售車輛", df_pending['vin'].tolist(), key=f"add_vehicles_{remit['r_id']}")
                        if st.button("➕ 帶入選中的車輛", key=f"add_btn_{remit['r_id']}"):
                            if selected_vins:
                                c = conn.cursor()
                                for vin in selected_vins:
                                    c.execute("UPDATE vehicle_master SET remit_id = ? WHERE vin = ?", (remit['r_id'], vin))
                                conn.commit()
                                st.success(f"已將 {len(selected_vins)} 台車輛帶入此匯款單")
                                st.rerun()
                    else:
                        st.info("目前無待售車輛可帶入")
        else:
            st.info("尚無匯款記錄")
        conn.close()
    
    with tab3:
        st.header("🚗 所有車輛匯款清單")
        conn = sqlite3.connect('haoyuan.db')
        # 取得所有有匯款單的車輛（JOIN 匯款單資訊）
        df_all_vehicles = pd.read_sql_query("""
            SELECT v.vin, v.engine, v.model, v.year, v.color, v.cost, v.profit, v.status,
                   r.r_id, r.r_date, r.vendor, r.total_amount, r.note
            FROM vehicle_master v
            LEFT JOIN remits r ON v.remit_id = r.r_id
            WHERE v.remit_id IS NOT NULL
            ORDER BY r.r_date DESC, v.vin
        """, conn)
        conn.close()
        
        if not df_all_vehicles.empty:
            # 匯款時間篩選
            col_filter1, col_filter2 = st.columns(2)
            start_remit_date = col_filter1.date_input("匯款開始日期", value=datetime(2024, 1, 1), key="remit_start_date")
            end_remit_date = col_filter2.date_input("匯款結束日期", value=datetime.now(), key="remit_end_date")
            
            # 應用篩選
            if 'r_date' in df_all_vehicles.columns:
                df_all_vehicles = df_all_vehicles[
                    (df_all_vehicles['r_date'].notna()) & 
                    (df_all_vehicles['r_date'] >= start_remit_date.strftime("%Y-%m-%d")) & 
                    (df_all_vehicles['r_date'] <= end_remit_date.strftime("%Y-%m-%d"))
                ]
            
            # 統計資訊
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            col_stat1.metric("車輛總數", len(df_all_vehicles))
            if 'profit' in df_all_vehicles.columns:
                total_profit = df_all_vehicles['profit'].sum() if df_all_vehicles['profit'].notna().any() else 0
                col_stat2.metric("總獲利", f"NT$ {total_profit:,.0f}")
            
            # 顯示清單（只顯示相關欄位）
            display_cols = ['vin', 'engine', 'model', 'year', 'color', 'r_date', 'vendor', 'r_id', 'total_amount', 'cost', 'profit', 'status']
            available_cols = [col for col in display_cols if col in df_all_vehicles.columns]
            # 重新命名欄位以更易讀
            df_display = df_all_vehicles[available_cols].copy()
            if 'r_id' in df_display.columns:
                df_display = df_display.rename(columns={
                    'vin': '車身號碼',
                    'engine': '引擎號碼',
                    'model': '車款',
                    'year': '年份',
                    'color': '顏色',
                    'r_date': '匯款日期',
                    'vendor': '廠商',
                    'r_id': '匯款單編號',
                    'total_amount': '匯款總額',
                    'cost': '成本',
                    'profit': '獲利',
                    'status': '狀態'
                })
            st.dataframe(df_display, use_container_width=True)
        else:
            st.info("尚無車輛匯款記錄")

# --- 6. 模組：新車進貨入庫（從歷史資料自動記憶年份/車款/顏色）---
elif menu == "📥 新車進貨入庫":
    st.header("📥 車輛入庫管理")
    
    # 初始化 session state
    if 'edit_vehicle_id' not in st.session_state:
        st.session_state.edit_vehicle_id = None
    
    # 顯示所有待售車輛清單，可選擇修改
    conn = sqlite3.connect('haoyuan.db')
    df_vehicles = pd.read_sql_query("""
        SELECT v.vin, v.engine, v.v_type, v.vendor, v.model, v.year, v.color, v.cost, v.inv_in, v.remit_id,
               r.r_date, r.vendor as remit_vendor
        FROM vehicle_master v
        LEFT JOIN remits r ON v.remit_id = r.r_id
        WHERE v.status='待售' 
        ORDER BY v.vin
    """, conn)
    
    if not df_vehicles.empty:
        st.subheader("📋 現有待售車輛清單（表格顯示，點選修改）")
        
        # 搜尋功能
        search_id = st.text_input("🔍 搜尋車身號碼/引擎號碼", key="search_vehicle_id")
        
        df_display = df_vehicles.copy()
        if search_id:
            df_display = df_display[
                (df_display['vin'].str.contains(search_id, case=False, na=False)) | 
                (df_display['engine'].str.contains(search_id, case=False, na=False))
            ]
        
        # 準備表格顯示資料
        df_table = df_display.copy()
        # 合併車身號碼/引擎號碼
        df_table['識別碼'] = df_table.apply(lambda row: row.get('vin') or row.get('engine') or '', axis=1)
        # 重新排列欄位順序
        display_columns = ['識別碼', 'v_type', 'vendor', 'model', 'year', 'color', 'cost', 'inv_in', 'remit_id', 'r_date']
        available_columns = [col for col in display_columns if col in df_table.columns]
        df_table_display = df_table[available_columns].copy()
        
        # 重新命名欄位為中文
        column_mapping = {
            '識別碼': '車身號碼/引擎號碼',
            'v_type': '車輛來源',
            'vendor': '廠商',
            'model': '車款',
            'year': '年份',
            'color': '顏色',
            'cost': '成本',
            'inv_in': '進貨發票',
            'remit_id': '匯款單編號',
            'r_date': '匯款日期'
        }
        df_table_display = df_table_display.rename(columns=column_mapping)
        
        # 格式化成本為貨幣格式
        if '成本' in df_table_display.columns:
            df_table_display['成本'] = df_table_display['成本'].apply(lambda x: f"NT$ {x:,.0f}" if pd.notna(x) and x != '' else '')
        
        # 顯示表格
        st.dataframe(df_table_display, use_container_width=True, height=400)
        
        # 選擇要修改的車輛（可從下拉選單選擇或自行填入）
        st.write("---")
        st.subheader("修改車輛資訊")
        st.info("💡 提示：您可以從下方下拉選單選擇車輛，或直接輸入車身號碼/引擎號碼，系統會自動載入該車輛的所有資訊")
        
        # 建立車輛選項列表（用於下拉選單）
        vehicle_options = []
        for _, row in df_display.iterrows():
            vehicle_id = row.get('vin') or row.get('engine') or ''
            vehicle_info = f"{vehicle_id} | {row.get('model', '')} - {row.get('year', '')} - {row.get('color', '')}"
            vehicle_options.append(vehicle_info)
        
        col_select1, col_select2 = st.columns([2, 1])
        with col_select1:
            if vehicle_options:
                # 找出當前選中車輛在列表中的索引
                selected_index = 0
                if st.session_state.edit_vehicle_id:
                    for idx, opt in enumerate(vehicle_options):
                        if st.session_state.edit_vehicle_id in opt:
                            selected_index = idx
                            break
                
                selected_vehicle_str = st.selectbox(
                    "從表格選擇車輛（或下方自行輸入）：",
                    options=["-- 請選擇或自行輸入 --"] + vehicle_options,
                    index=selected_index + 1 if st.session_state.edit_vehicle_id else 0,
                    key="vehicle_select_dropdown"
                )
                
                # 如果從下拉選單選擇了車輛，自動填入輸入框
                if selected_vehicle_str and selected_vehicle_str != "-- 請選擇或自行輸入 --":
                    # 從選項字串中提取識別碼（第一個部分，在 | 之前）
                    auto_filled_id = selected_vehicle_str.split(' | ')[0].strip()
                    if auto_filled_id:
                        # 直接設置session_state並觸發載入
                        if st.session_state.get('edit_vehicle_id') != auto_filled_id:
                            # 清除表單狀態
                            form_keys_to_clear = [
                                'year_select', 'year_input_new',
                                'model_select', 'model_input_new',
                                'color_select', 'color_input_new',
                                'vehicle_id_input',
                                'cost_input'
                            ]
                            for key in form_keys_to_clear:
                                if key in st.session_state:
                                    del st.session_state[key]
                            
                            st.session_state.edit_vehicle_id = auto_filled_id
                            st.rerun()
        
        # 定義自動載入函數
        def auto_load_vehicle():
            """自動載入車輛資料的函數"""
            input_value = st.session_state.get('edit_vehicle_input', '').strip()
            if input_value:
                # 檢查輸入的識別碼是否在資料庫中存在
                conn_check = sqlite3.connect('haoyuan.db')
                check_query = pd.read_sql_query("""
                    SELECT vin, engine 
                    FROM vehicle_master 
                    WHERE (vin = ? OR engine = ?) AND status = '待售'
                    LIMIT 1
                """, conn_check, params=(input_value, input_value))
                conn_check.close()
                
                if not check_query.empty:
                    # 找到車輛，自動載入
                    found_vehicle_id = check_query.iloc[0].get('vin') or check_query.iloc[0].get('engine') or input_value
                    if st.session_state.get('edit_vehicle_id') != found_vehicle_id:
                        # 清除之前的表單狀態，確保新車輛資料能正確載入
                        form_keys_to_clear = [
                            'year_select', 'year_input_new',
                            'model_select', 'model_input_new',
                            'color_select', 'color_input_new',
                            'vehicle_id_input',
                            'cost_input'
                        ]
                        for key in form_keys_to_clear:
                            if key in st.session_state:
                                del st.session_state[key]
                        
                        # 設定新的車輛ID
                        st.session_state.edit_vehicle_id = found_vehicle_id
                        st.rerun()
            else:
                # 如果輸入框為空，清除編輯狀態
                if st.session_state.get('edit_vehicle_id'):
                    st.session_state.edit_vehicle_id = None
                    # 清除表單狀態
                    form_keys_to_clear = [
                        'year_select', 'year_input_new',
                        'model_select', 'model_input_new',
                        'color_select', 'color_input_new',
                        'vehicle_id_input',
                        'cost_input'
                    ]
                    for key in form_keys_to_clear:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
        
        edit_input_id = st.text_input(
            "或直接輸入要修改的車輛識別碼（車身號碼/引擎號碼）：",
            key="edit_vehicle_input",
            placeholder="請輸入車身號碼或引擎號碼，系統會自動載入",
            value=st.session_state.edit_vehicle_id if st.session_state.edit_vehicle_id else "",
            on_change=auto_load_vehicle
        )
        
        # 如果輸入框的值改變（且與當前載入的不同），嘗試自動載入
        # 這是在 on_change 之外的額外檢查，確保即使 on_change 沒有觸發也能工作
        if edit_input_id and edit_input_id.strip():
            current_input = edit_input_id.strip()
            current_loaded = st.session_state.get('edit_vehicle_id', '') or ''
            
            # 如果輸入的值與當前載入的不同，檢查是否需要載入
            if current_input != current_loaded:
                # 檢查是否在資料庫中存在
                conn_auto_check = sqlite3.connect('haoyuan.db')
                auto_check_query = pd.read_sql_query("""
                    SELECT vin, engine 
                    FROM vehicle_master 
                    WHERE (vin = ? OR engine = ?) AND status = '待售'
                    LIMIT 1
                """, conn_auto_check, params=(current_input, current_input))
                conn_auto_check.close()
                
                if not auto_check_query.empty:
                    # 找到車輛，自動載入
                    found_vehicle_id = auto_check_query.iloc[0].get('vin') or auto_check_query.iloc[0].get('engine') or current_input
                    if st.session_state.get('edit_vehicle_id') != found_vehicle_id:
                        # 清除之前的表單狀態
                        form_keys_to_clear = [
                            'year_select', 'year_input_new',
                            'model_select', 'model_input_new',
                            'color_select', 'color_input_new',
                            'vehicle_id_input',
                            'cost_input'
                        ]
                        for key in form_keys_to_clear:
                            if key in st.session_state:
                                del st.session_state[key]
                        
                        st.session_state.edit_vehicle_id = found_vehicle_id
                        st.rerun()
        
        col_btn1, col_btn2 = st.columns([1, 5])
        with col_btn1:
            if st.button("✏️ 手動載入", key="edit_selected_btn", use_container_width=True, help="如果自動載入失敗，可點擊此按鈕手動載入"):
                if edit_input_id and edit_input_id.strip():
                    # 清除之前的表單狀態，確保新車輛資料能正確載入
                    form_keys_to_clear = [
                        'year_select', 'year_input_new',
                        'model_select', 'model_input_new',
                        'color_select', 'color_input_new',
                        'vehicle_id_input',
                        'cost_input'
                    ]
                    for key in form_keys_to_clear:
                        if key in st.session_state:
                            del st.session_state[key]
                    
                    # 設定新的車輛ID
                    st.session_state.edit_vehicle_id = edit_input_id.strip()
                    st.rerun()
                else:
                    st.error("請輸入車身號碼或引擎號碼")
        with col_btn2:
            if st.session_state.edit_vehicle_id:
                if st.button("❌ 取消編輯", key="cancel_edit_btn", use_container_width=True):
                    # 清除刪除確認狀態
                    delete_confirm_key = f"delete_confirm_{st.session_state.edit_vehicle_id}"
                    if delete_confirm_key in st.session_state:
                        del st.session_state[delete_confirm_key]
                    st.session_state.edit_vehicle_id = None
                    st.rerun()
        
        st.write("---")
    
    # 如果是編輯模式，載入現有資料（從完整資料表重新查詢以確保載入所有資訊）
    edit_vehicle_data = {}
    if st.session_state.edit_vehicle_id:
        conn_edit = sqlite3.connect('haoyuan.db')
        edit_vehicle_query = pd.read_sql_query("""
            SELECT vin, engine, v_type, vendor, model, year, color, cost, inv_in, remit_id
            FROM vehicle_master
            WHERE (vin = ? OR engine = ?) AND status = '待售'
        """, conn_edit, params=(st.session_state.edit_vehicle_id, st.session_state.edit_vehicle_id))
        conn_edit.close()
        
        if not edit_vehicle_query.empty:
            edit_vehicle_data = edit_vehicle_query.iloc[0].to_dict()
            vehicle_id_display = edit_vehicle_data.get('vin') or edit_vehicle_data.get('engine') or st.session_state.edit_vehicle_id
            st.success(f"✏️ 已載入車輛資料：{vehicle_id_display} | {edit_vehicle_data.get('model', '')} - {edit_vehicle_data.get('year', '')} - {edit_vehicle_data.get('color', '')}")
            
            # 顯示操作按鈕（修改/刪除）
            col_action1, col_action2, col_action3 = st.columns([2, 1, 1])
            with col_action1:
                st.info("💡 現在可以修改下方的車輛資訊")
            with col_action2:
                # 刪除確認狀態
                delete_confirm_key = f"delete_confirm_{st.session_state.edit_vehicle_id}"
                if delete_confirm_key not in st.session_state:
                    st.session_state[delete_confirm_key] = False
                
                if not st.session_state[delete_confirm_key]:
                    if st.button("🗑️ 刪除車輛", key="delete_vehicle_btn", type="primary", use_container_width=True):
                        st.session_state[delete_confirm_key] = True
                        st.rerun()
                else:
                    if st.button("✅ 確認刪除", key="confirm_delete_btn", type="primary", use_container_width=True):
                        # 執行刪除
                        conn_delete = sqlite3.connect('haoyuan.db')
                        c_delete = conn_delete.cursor()
                        vehicle_to_delete = st.session_state.edit_vehicle_id
                        c_delete.execute("DELETE FROM vehicle_master WHERE (vin=? OR engine=?) AND status='待售'", 
                                       (vehicle_to_delete, vehicle_to_delete))
                        deleted_count = c_delete.rowcount
                        conn_delete.commit()
                        conn_delete.close()
                        
                        if deleted_count > 0:
                            st.success(f"✅ 車輛「{vehicle_id_display}」已刪除")
                        else:
                            st.warning(f"⚠️ 無法刪除車輛「{vehicle_id_display}」，可能已被刪除或狀態不是待售")
                        
                        st.session_state.edit_vehicle_id = None
                        st.session_state[delete_confirm_key] = False
                        # 清除表單相關的 session_state
                        form_keys_to_clear = [
                            'year_select', 'year_input_new',
                            'model_select', 'model_input_new',
                            'color_select', 'color_input_new',
                            'vehicle_id_input',
                            'cost_input',
                            'edit_vehicle_input'
                        ]
                        for key in form_keys_to_clear:
                            if key in st.session_state:
                                del st.session_state[key]
                        st.rerun()
            with col_action3:
                if st.session_state.get(delete_confirm_key, False):
                    if st.button("❌ 取消", key="cancel_delete_btn", use_container_width=True):
                        st.session_state[delete_confirm_key] = False
                        st.rerun()
            
            if st.session_state.get(delete_confirm_key, False):
                st.warning(f"⚠️ 確定要刪除車輛「{vehicle_id_display}」嗎？此操作無法復原！請點擊「✅ 確認刪除」完成刪除，或點擊「❌ 取消」取消操作。")
        else:
            missing_vehicle_id = st.session_state.edit_vehicle_id
            st.warning(f"找不到車輛：{missing_vehicle_id}，可能已被刪除或狀態不是待售")
            # 清除可能的刪除確認狀態（在設置edit_vehicle_id為None之前）
            delete_confirm_key = f"delete_confirm_{missing_vehicle_id}"
            if delete_confirm_key in st.session_state:
                del st.session_state[delete_confirm_key]
            st.session_state.edit_vehicle_id = None
    
    conn.close()
    
    # 只有在編輯模式下才顯示表單（如果沒有選擇編輯，則只顯示提示）
    if not st.session_state.edit_vehicle_id:
        st.info("👆 請先在上方輸入要修改的車輛識別碼並點擊「載入車輛資料」，然後才能修改車輛資訊")
    
    with st.form("in_form"):
        c1, c2, c3 = st.columns(3)
        v_type = c1.selectbox("車輛來源", ["公司車", "貿易車", "中古車"], index=["公司車", "貿易車", "中古車"].index(edit_vehicle_data.get('v_type', '公司車')) if edit_vehicle_data.get('v_type') in ["公司車", "貿易車", "中古車"] else 0)
        vendor_opts = get_vendors()
        v_vendor = c1.selectbox("廠商", vendor_opts if vendor_opts else ["請先到系統設定新增廠商"], 
                                index=vendor_opts.index(edit_vehicle_data.get('vendor', '')) if vendor_opts and edit_vehicle_data.get('vendor') in vendor_opts else 0)
        
        # 從歷史資料自動獲取年份/車款/顏色選項（下拉式選單，可新增）
        year_opts = get_historical_options('year')
        year_default = edit_vehicle_data.get('year', '') if edit_vehicle_data else ''
        year_options = year_opts if year_opts else []
        # 添加「➕ 新增...」選項，並將現有值加入選項（如果不在歷史選項中）
        if year_default and year_default not in year_options:
            year_options = [year_default] + year_options
        year_options = year_options + ["➕ 新增..."]
        
        # 設定預設索引（如果有載入的車輛資料，優先使用該值）
        year_index = len(year_options) - 1  # 預設選擇「➕ 新增...」
        if year_default:
            if year_default in year_options:
                year_index = year_options.index(year_default)
            else:
                # 如果值不在選項中，插入到第一個位置並選擇它
                year_options.insert(0, year_default)
                year_index = 0
        
        # 如果key存在但我們有新的車輛資料，強制使用新資料（清除key後重新建立）
        year_key = "year_select"
        if year_key in st.session_state and year_default:
            # 確保selectbox會使用新載入的資料
            if st.session_state[year_key] != year_default and year_default in year_options:
                # 如果session_state中的值與新資料不符，更新它
                st.session_state[year_key] = year_default
        
        year_selected = c2.selectbox("年份", options=year_options, index=year_index, key=year_key)
        if year_selected == "➕ 新增...":
            v_year = c2.text_input("📝 請輸入新年份", key="year_input_new", placeholder="例如：2024")
        else:
            v_year = year_selected if year_selected else ""
        
        model_opts = get_historical_options('model')
        model_default = edit_vehicle_data.get('model', '') if edit_vehicle_data else ''
        model_options = model_opts if model_opts else []
        if model_default and model_default not in model_options:
            model_options = [model_default] + model_options
        model_options = model_options + ["➕ 新增..."]
        
        model_index = len(model_options) - 1  # 預設選擇「➕ 新增...」
        if model_default:
            if model_default in model_options:
                model_index = model_options.index(model_default)
            else:
                model_options.insert(0, model_default)
                model_index = 0
        
        model_key = "model_select"
        if model_key in st.session_state and model_default:
            if st.session_state[model_key] != model_default and model_default in model_options:
                st.session_state[model_key] = model_default
        
        model_selected = c2.selectbox("車款", options=model_options, index=model_index, key=model_key)
        if model_selected == "➕ 新增...":
            v_model = c2.text_input("📝 請輸入新車款", key="model_input_new", placeholder="例如：XMAX")
        else:
            v_model = model_selected if model_selected else ""
        
        color_opts = get_historical_options('color')
        color_default = edit_vehicle_data.get('color', '') if edit_vehicle_data else ''
        color_options = color_opts if color_opts else []
        if color_default and color_default not in color_options:
            color_options = [color_default] + color_options
        color_options = color_options + ["➕ 新增..."]
        
        color_index = len(color_options) - 1  # 預設選擇「➕ 新增...」
        if color_default:
            if color_default in color_options:
                color_index = color_options.index(color_default)
            else:
                color_options.insert(0, color_default)
                color_index = 0
        
        color_key = "color_select"
        if color_key in st.session_state and color_default:
            if st.session_state[color_key] != color_default and color_default in color_options:
                st.session_state[color_key] = color_default
        
        color_selected = c3.selectbox("顏色", options=color_options, index=color_index, key=color_key)
        if color_selected == "➕ 新增...":
            v_color = c3.text_input("📝 請輸入新顏色", key="color_input_new", placeholder="例如：白色")
        else:
            v_color = color_selected if color_selected else ""
        
        st.write("---")
        # 車身號碼/引擎號碼（合併為同一欄位）
        existing_id = edit_vehicle_data.get('vin') or edit_vehicle_data.get('engine') or ''
        vehicle_id = st.text_input("車身號碼/引擎號碼", key="vehicle_id_input", placeholder="請輸入車身號碼或引擎號碼", value=existing_id)
        v_vin = vehicle_id
        v_engine = vehicle_id
        
        st.write("---")
        # 關聯匯款單（過濾已全部入庫的匯款單）
        conn = sqlite3.connect('haoyuan.db')
        df_r = pd.read_sql_query("SELECT r_id, r_date, vendor, total_amount FROM remits ORDER BY r_date DESC", conn)
        
        # 檢查每個匯款單是否已全部入庫
        available_remits = []
        for _, remit in df_r.iterrows():
            r_id = remit['r_id']
            # 取得匯款項目總數
            df_items = pd.read_sql_query("SELECT SUM(quantity) as total_qty FROM remit_items WHERE r_id=?", 
                                        conn, params=(r_id,))
            total_expected = df_items['total_qty'].iloc[0] if not df_items.empty and df_items['total_qty'].iloc[0] is not None else 0
            
            # 取得已入庫車輛數
            df_in_stock = pd.read_sql_query("SELECT COUNT(*) as count FROM vehicle_master WHERE remit_id=?", 
                                           conn, params=(r_id,))
            total_in_stock = df_in_stock['count'].iloc[0] if not df_in_stock.empty else 0
            
            # 如果未全部入庫，則加入選項
            if total_in_stock < total_expected or total_expected == 0:
                available_remits.append(remit)
        
        conn.close()
        
        # 取得當前車輛關聯的匯款單編號
        current_remit_id = edit_vehicle_data.get('remit_id') if edit_vehicle_data else None
        remit_id_val = None
        
        if available_remits:
            r_options = ["不關聯/手填"] + [f"{int(row['r_id'])} - {row['vendor']} ({row['r_date']})" for _, row in pd.DataFrame(available_remits).iterrows()]
            # 如果當前車輛有關聯匯款單，預設選擇該匯款單
            default_index = 0
            if current_remit_id:
                for idx, remit in enumerate(available_remits):
                    if remit['r_id'] == current_remit_id:
                        default_index = idx + 1  # +1 因為第一個是"不關聯/手填"
                        break
            r_choice = st.selectbox("關聯老闆娘匯款單", r_options, index=default_index)
        else:
            r_choice = "不關聯/手填"
            if not df_r.empty:
                st.info("所有匯款單的車輛都已入庫")
            else:
                st.info("尚無匯款單，請先到「老闆娘匯款中心」建立匯款單")
        
        # 根據選擇的匯款單和車款自動填入成本
        remit_id_val = None
        if r_choice != "不關聯/手填":
            selected_r_id = int(r_choice.split(" - ")[0])
            remit_id_val = selected_r_id
            
            # 如果選擇了匯款單且有車款，嘗試自動帶入成本
            if v_model:
                conn_cost = sqlite3.connect('haoyuan.db')
                df_item = pd.read_sql_query("SELECT unit_price FROM remit_items WHERE r_id=? AND model=?", 
                                           conn_cost, params=(selected_r_id, v_model))
                conn_cost.close()
                if not df_item.empty:
                    existing_cost = float(df_item['unit_price'].iloc[0])
                else:
                    existing_cost = edit_vehicle_data.get('cost', 0.0) if edit_vehicle_data else 0.0
            else:
                existing_cost = edit_vehicle_data.get('cost', 0.0) if edit_vehicle_data else 0.0
        else:
            existing_cost = edit_vehicle_data.get('cost', 0.0) if edit_vehicle_data else 0.0
        
        v_cost = st.number_input("成本", value=float(existing_cost), key="cost_input")
        
        existing_inv_in = edit_vehicle_data.get('inv_in', '') if edit_vehicle_data else ''
        v_inv_in = st.text_input("進貨發票號碼", value=existing_inv_in)
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            submit_text = "修改車輛" if st.session_state.edit_vehicle_id else "車輛入庫"
            if st.form_submit_button(submit_text, use_container_width=True):
                # 處理空字串（如果使用下拉選單且選擇了空選項）
                v_year = v_year if v_year and v_year != "" else None
                v_model = v_model if v_model and v_model != "" else None
                v_color = v_color if v_color and v_color != "" else None
                
                # 確保填寫了車身號碼/引擎號碼和車款
                vehicle_id_clean = vehicle_id.strip() if vehicle_id and vehicle_id.strip() != "" else None
                
                if vehicle_id_clean and v_model:
                    conn = sqlite3.connect('haoyuan.db')
                    is_duplicate = False
                    duplicate_info = ""
                    
                    # 檢查重複的車身號碼/引擎號碼
                    if st.session_state.edit_vehicle_id:
                        # 修改模式：檢查新號碼是否與其他車輛重複（排除自己）
                        old_vehicle_id = st.session_state.edit_vehicle_id
                        
                        # 如果新號碼與舊號碼不同，需要檢查是否被其他車輛使用
                        if vehicle_id_clean != old_vehicle_id:
                            check_duplicate = pd.read_sql_query("""
                                SELECT vin, engine, model, year, color, status 
                                FROM vehicle_master 
                                WHERE (vin = ? OR engine = ?) 
                                AND (vin != ? AND engine != ?)
                            """, conn, params=(vehicle_id_clean, vehicle_id_clean, old_vehicle_id, old_vehicle_id))
                            
                            if not check_duplicate.empty:
                                dup_vehicle = check_duplicate.iloc[0]
                                is_duplicate = True
                                dup_status = dup_vehicle.get('status', '')
                                dup_info = f"{dup_vehicle.get('model', '')} - {dup_vehicle.get('year', '')} - {dup_vehicle.get('color', '')} (狀態: {dup_status})"
                                duplicate_info = f"⚠️ 錯誤：車身號碼/引擎號碼「{vehicle_id_clean}」已被其他車輛使用！\n\n已存在車輛資訊：{dup_info}\n\n請檢查輸入的號碼是否正確，或先刪除/修改現有的車輛記錄。"
                    else:
                        # 新增模式：檢查是否已存在相同的號碼
                        check_duplicate = pd.read_sql_query("""
                            SELECT vin, engine, model, year, color, status 
                            FROM vehicle_master 
                            WHERE vin = ? OR engine = ?
                        """, conn, params=(vehicle_id_clean, vehicle_id_clean))
                        
                        if not check_duplicate.empty:
                            dup_vehicle = check_duplicate.iloc[0]
                            is_duplicate = True
                            dup_status = dup_vehicle.get('status', '')
                            dup_info = f"{dup_vehicle.get('model', '')} - {dup_vehicle.get('year', '')} - {dup_vehicle.get('color', '')} (狀態: {dup_status})"
                            duplicate_info = f"⚠️ 錯誤：車身號碼/引擎號碼「{vehicle_id_clean}」已存在！\n\n已存在車輛資訊：{dup_info}\n\n請檢查輸入的號碼是否正確，或使用「修改車輛資訊」功能來更新現有記錄。"
                    
                    # 如果有重複，顯示錯誤訊息並阻止入庫
                    if is_duplicate:
                        st.error(duplicate_info)
                        conn.close()
                    else:
                        # 沒有重複，允許入庫/修改
                        # 如果是編輯模式且號碼改變，需要先刪除舊的記錄
                        if st.session_state.edit_vehicle_id and st.session_state.edit_vehicle_id != vehicle_id_clean:
                            # 刪除舊記錄
                            conn.execute("DELETE FROM vehicle_master WHERE (vin=? OR engine=?) AND vin=?", 
                                       (st.session_state.edit_vehicle_id, st.session_state.edit_vehicle_id, st.session_state.edit_vehicle_id))
                        
                        conn.execute("""INSERT OR REPLACE INTO vehicle_master (vin, engine, v_type, vendor, brand, model, year, color, cost, inv_in, remit_id, status) 
                                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                                     (vehicle_id_clean, vehicle_id_clean, v_type, v_vendor, "", v_model, v_year, v_color, v_cost, v_inv_in, remit_id_val, "待售"))
                        conn.commit()
                        conn.close()
                        st.success("車輛已" + ("修改" if st.session_state.edit_vehicle_id else "入庫"))
                        
                        # 清除所有表單相關的 session_state（確保表單重置）
                        was_editing = st.session_state.edit_vehicle_id is not None
                        st.session_state.edit_vehicle_id = None
                        
                        # 清除編輯輸入框的值
                        if 'edit_vehicle_id_input' in st.session_state:
                            st.session_state.edit_vehicle_id_input = ""
                        
                        # 清除表單輸入框的key（這樣下次渲染時會使用預設值）
                        form_keys_to_clear = [
                            'year_select', 'year_input_new',
                            'model_select', 'model_input_new',
                            'color_select', 'color_input_new',
                            'vehicle_id_input',
                            'cost_input'
                        ]
                        for key in form_keys_to_clear:
                            if key in st.session_state:
                                del st.session_state[key]
                        
                        st.rerun()
                else:
                    if not vehicle_id_clean:
                        st.error("請輸入車身號碼/引擎號碼")
                    if not v_model:
                        st.error("請輸入車款")
        with col_btn2:
            if st.session_state.edit_vehicle_id:
                if st.form_submit_button("取消編輯", use_container_width=True):
                    st.session_state.edit_vehicle_id = None
                    st.rerun()

# --- 7. 模組：業務銷售專區 ---
elif menu == "🤝 業務銷售專區":
    tab1, tab2, tab3 = st.tabs(["🚗 新車銷售", "📊 業務銷售清單", "✏️ 修改/刪除銷售記錄"])
    
    with tab1:
        st.header("🚗 新車銷售")
        
        # 取得所有車輛（已售+待售）
        conn = sqlite3.connect('haoyuan.db')
        df_all_vehicles = pd.read_sql_query("""
            SELECT vin, engine, v_type, vendor, brand, model, year, color, cost, status, 
                   cust_name, cust_phone, plate_no, out_date, sales_person, profit
            FROM vehicle_master
            ORDER BY status DESC, vin
        """, conn)
        
        # 初始化 session state
        if 'selected_vin' not in st.session_state:
            st.session_state.selected_vin = None
        
        if not df_all_vehicles.empty:
            # 顯示車輛清單
            st.subheader("📋 所有車輛清單（點選車輛進行銷售結案）")
            
            # 狀態篩選
            col_filter1, col_filter2 = st.columns(2)
            with col_filter1:
                status_filter = col_filter1.multiselect(
                    "狀態篩選", 
                    ["待售", "已售"], 
                    default=["待售", "已售"],
                    key="sale_status_filter"
                )
            with col_filter2:
                search_vin = col_filter2.text_input("🔍 搜尋車身號碼/引擎號碼", key="sale_search_vin")
            
            # 應用篩選
            df_filtered = df_all_vehicles.copy()
            if status_filter:
                df_filtered = df_filtered[df_filtered['status'].isin(status_filter)]
            if search_vin:
                df_filtered = df_filtered[
                    (df_filtered['vin'].str.contains(search_vin, case=False, na=False)) |
                    (df_filtered['engine'].str.contains(search_vin, case=False, na=False))
                ]
            
            # 統計資訊
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            col_stat1.metric("總車輛數", len(df_filtered))
            col_stat2.metric("待售", len(df_filtered[df_filtered['status'] == '待售']) if 'status' in df_filtered.columns else 0)
            col_stat3.metric("已售", len(df_filtered[df_filtered['status'] == '已售']) if 'status' in df_filtered.columns else 0)
            
            # 準備表格顯示資料
            df_table = df_filtered.copy()
            # 合併車身號碼/引擎號碼
            df_table['識別碼'] = df_table.apply(lambda row: row.get('vin') or row.get('engine') or '', axis=1)
            # 添加狀態標記
            df_table['狀態'] = df_table['status'].apply(lambda x: '🟢 待售' if x == '待售' else '🔴 已售')
            
            # 選擇要顯示的欄位
            display_columns = ['狀態', '識別碼', 'v_type', 'vendor', 'model', 'year', 'color', 'cost']
            if 'sales_person' in df_table.columns:
                display_columns.append('sales_person')
            if 'profit' in df_table.columns:
                display_columns.append('profit')
            if 'plate_no' in df_table.columns:
                display_columns.append('plate_no')
            if 'cust_name' in df_table.columns:
                display_columns.append('cust_name')
            if 'out_date' in df_table.columns:
                display_columns.append('out_date')
            
            available_columns = [col for col in display_columns if col in df_table.columns]
            df_table_display = df_table[available_columns].copy()
            
            # 重新命名欄位為中文
            column_mapping = {
                '狀態': '狀態',
                '識別碼': '車身號碼/引擎號碼',
                'v_type': '車輛來源',
                'vendor': '廠商',
                'model': '車款',
                'year': '年份',
                'color': '顏色',
                'cost': '成本',
                'sales_person': '業務人員',
                'profit': '獲利',
                'plate_no': '車牌號碼',
                'cust_name': '顧客姓名',
                'out_date': '領牌日'
            }
            df_table_display = df_table_display.rename(columns=column_mapping)
            
            # 格式化數字欄位
            if '成本' in df_table_display.columns:
                df_table_display['成本'] = df_table_display['成本'].apply(
                    lambda x: f"NT$ {float(x):,.0f}" if pd.notna(x) and x != '' and x != 'NT$ 0' and isinstance(x, (int, float)) else (x if isinstance(x, str) and 'NT$' in str(x) else f"NT$ {float(x):,.0f}" if pd.notna(x) else 'NT$ 0')
                )
            if '獲利' in df_table_display.columns:
                df_table_display['獲利'] = df_table_display['獲利'].apply(
                    lambda x: f"NT$ {float(x):,.0f}" if pd.notna(x) and x != '' and isinstance(x, (int, float)) else (x if isinstance(x, str) and 'NT$' in str(x) else '')
                )
            
            # 顯示表格
            st.dataframe(df_table_display, use_container_width=True, height=400)
            
            # 選擇要進行銷售的車輛（自行填入）
            st.write("---")
            sale_input_id = st.text_input(
                "輸入要進行銷售的車輛識別碼（車身號碼/引擎號碼）：",
                key="sale_vehicle_input",
                placeholder="請輸入車身號碼或引擎號碼",
                value=st.session_state.selected_vin if st.session_state.selected_vin else ""
            )
            
            col_btn1, col_btn2 = st.columns([1, 5])
            with col_btn1:
                if sale_input_id and sale_input_id.strip():
                    # 在篩選後的資料中尋找匹配的車輛
                    matched_vehicle = df_filtered[
                        (df_filtered['vin'].str.contains(sale_input_id.strip(), case=False, na=False)) |
                        (df_filtered['engine'].str.contains(sale_input_id.strip(), case=False, na=False))
                    ]
                    
                    if not matched_vehicle.empty:
                        matched_row = matched_vehicle.iloc[0]
                        if matched_row.get('status') == '待售':
                            if st.button("✏️ 銷售", key="sale_selected_btn", use_container_width=True):
                                st.session_state.selected_vin = matched_row.get('vin')
                                st.rerun()
                        else:
                            if st.button("👁️ 查看", key="view_selected_btn", use_container_width=True):
                                st.session_state.selected_vin = matched_row.get('vin')
                                st.rerun()
                    else:
                        if st.button("✏️ 銷售", key="sale_selected_btn", disabled=True, use_container_width=True):
                            pass
                        st.warning("找不到匹配的車輛，請檢查輸入的識別碼")
                else:
                    if st.button("✏️ 銷售", key="sale_selected_btn", disabled=True, use_container_width=True):
                        pass
                    st.info("請輸入車身號碼或引擎號碼")
            
            if df_filtered.empty:
                st.info("沒有符合條件的車輛")
                st.session_state.selected_vin = None
        
        # 如果選擇了車輛，顯示銷售表單
        if st.session_state.selected_vin:
            sel_vin = st.session_state.selected_vin
            # 取得選中車輛的詳細資訊
            selected_vehicle = df_all_vehicles[df_all_vehicles['vin'] == sel_vin].iloc[0]
            
            # 合併顯示車身號碼/引擎號碼
            vehicle_id_display = selected_vehicle.get('vin') or selected_vehicle.get('engine') or sel_vin
            
            # 檢查車輛狀態
            if selected_vehicle['status'] == '已售':
                st.warning(f"⚠️ 車輛 {vehicle_id_display} 已經結案（已售），如需修改請到「修改/刪除銷售記錄」分頁")
                st.info(f"**車輛資訊：** {selected_vehicle.get('model', '')} - {selected_vehicle.get('year', '')} - {selected_vehicle.get('color', '')}")
                if 'sales_person' in selected_vehicle and pd.notna(selected_vehicle['sales_person']):
                    st.info(f"**業務人員：** {selected_vehicle['sales_person']}")
                if 'profit' in selected_vehicle and pd.notna(selected_vehicle['profit']):
                    st.info(f"**獲利：** NT$ {selected_vehicle['profit']:,.0f}")
            else:
                # 待售車輛，顯示銷售表單
                st.subheader(f"📝 新車銷售表單 - 車輛：{vehicle_id_display}")
                st.info(f"**車身號碼/引擎號碼：** {vehicle_id_display} | **車輛資訊：** {selected_vehicle.get('model', '')} - {selected_vehicle.get('year', '')} - {selected_vehicle.get('color', '')} | **成本：** NT$ {selected_vehicle.get('cost', 0):,.0f}")
                
                try:
                    df_parts = pd.read_sql_query("SELECT part_name, cost FROM inventory", conn)
                except:
                    df_parts = pd.DataFrame()
                
                with st.form("sale_form"):
                    c1, c2 = st.columns(2)
                    sales_opts = get_sales_persons()
                    if sales_opts:
                        sales_person = c1.selectbox("業務人員姓名 *", options=[""] + sales_opts, key="sales_person_tab1")
                    else:
                        sales_person = c1.text_input("業務人員姓名 * (請到系統設定新增業務)", key="sales_person_tab1")
                    c_name = c1.text_input("顧客姓名")
                    c_phone = c1.text_input("顧客電話")
                    c_bday = c2.date_input("顧客生日")
                    c_addr = c2.text_input("顧客地址")
                    
                    st.write("---")
                    out_date = st.date_input("領牌日")
                    out_plate = st.text_input("車牌號碼")
                    out_inv = st.text_input("銷項發票號碼")
                    out_price = st.number_input("成交金額", min_value=0)
                    
                    st.write("---")
                    f_subsidy = st.number_input("分期補貼息成本", value=0.0)
                    acc_credit = st.number_input("贈送改裝金金額", value=0.0)
                    if not df_parts.empty:
                        sel_parts = st.multiselect("選取加裝配件 (計算改裝成本)", df_parts['part_name'].tolist())
                    else:
                        sel_parts = []
                        st.info("尚無零件資料，請先到倉管系統新增零件")
                    
                    st.write("---")
                    st.write("**上傳四樣文件：**")
                    file_col1, file_col2 = st.columns(2)
                    with file_col1:
                        file_license = st.file_uploader("📄 行照", type=['png', 'jpg', 'jpeg', 'pdf'], key="file_license_tab1")
                        if file_license:
                            if file_license.type.startswith('image/'):
                                st.image(file_license, caption="行照預覽", width=200)
                            else:
                                st.info(f"已上傳：{file_license.name}")
                        file_invoice = st.file_uploader("🧾 發票", type=['png', 'jpg', 'jpeg', 'pdf'], key="file_invoice_tab1")
                        if file_invoice:
                            if file_invoice.type.startswith('image/'):
                                st.image(file_invoice, caption="發票預覽", width=200)
                            else:
                                st.info(f"已上傳：{file_invoice.name}")
                    with file_col2:
                        file_registration = st.file_uploader("📋 領牌登記書", type=['png', 'jpg', 'jpeg', 'pdf'], key="file_registration_tab1")
                        if file_registration:
                            if file_registration.type.startswith('image/'):
                                st.image(file_registration, caption="領牌登記書預覽", width=200)
                            else:
                                st.info(f"已上傳：{file_registration.name}")
                        file_original = st.file_uploader("📎 原始資料", type=['png', 'jpg', 'jpeg', 'pdf'], key="file_original_tab1")
                        if file_original:
                            if file_original.type.startswith('image/'):
                                st.image(file_original, caption="原始資料預覽", width=200)
                            else:
                                st.info(f"已上傳：{file_original.name}")

                    if st.form_submit_button("🏁 確認結案"):
                        # 計算：成交價 - 車成本 - 分期息 - 改裝品成本
                        car_cost = selected_vehicle.get('cost', 0)
                        if not df_parts.empty:
                            acc_cost = df_parts[df_parts['part_name'].isin(sel_parts)]['cost'].sum()
                        else:
                            acc_cost = 0
                        net_profit = out_price - car_cost - f_subsidy - acc_cost
                        
                        if not sales_person:
                            st.error("請輸入業務人員姓名")
                        else:
                            # 保存上傳的檔案
                            upload_dir = "uploads"
                            os.makedirs(upload_dir, exist_ok=True)
                            
                            file_paths = {}
                            # 使用實際的檔案變數
                            file_mapping = {
                                'file_license': file_license,
                                'file_invoice': file_invoice,
                                'file_registration': file_registration,
                                'file_original': file_original
                            }
                            file_names = {
                                'file_license': '行照',
                                'file_invoice': '發票',
                                'file_registration': '領牌登記書',
                                'file_original': '原始資料'
                            }
                            
                            for file_key, file_obj in file_mapping.items():
                                if file_obj is not None:
                                    # 生成檔案名稱：VIN_檔案類型_原始檔名
                                    file_ext = os.path.splitext(file_obj.name)[1]
                                    save_filename = f"{sel_vin}_{file_names[file_key]}{file_ext}"
                                    save_path = os.path.join(upload_dir, save_filename)
                                    with open(save_path, "wb") as f:
                                        f.write(file_obj.getbuffer())
                                    file_paths[file_key] = save_path
                                else:
                                    file_paths[file_key] = None
                            
                            conn = sqlite3.connect('haoyuan.db')
                            c = conn.cursor()
                            for p in sel_parts:
                                try:
                                    c.execute("UPDATE inventory SET stock = stock - 1 WHERE part_name=?", (p,))
                                except:
                                    pass
                            c.execute("""UPDATE vehicle_master SET cust_name=?, cust_phone=?, cust_birthday=?, cust_address=?, 
                                         out_date=?, plate_no=?, inv_out=?, finance_subsidy=?, acc_credit=?, profit=?, status='已售', sales_person=?,
                                         file_license=?, file_invoice=?, file_registration=?, file_original=?
                                         WHERE vin=?""", 
                                     (c_name, c_phone, c_bday.strftime("%Y-%m-%d") if c_bday else None, c_addr, 
                                      out_date.strftime("%Y-%m-%d") if out_date else None, out_plate, out_inv, 
                                      f_subsidy, acc_credit, net_profit, sales_person,
                                      file_paths.get('file_license'), file_paths.get('file_invoice'), 
                                      file_paths.get('file_registration'), file_paths.get('file_original'),
                                      sel_vin))
                            conn.commit()
                            conn.close()
                            st.balloons()
                            st.success(f"結案完成！此台獲利：{net_profit:,.0f}")
                            # 清空選中的車輛，以便重新選擇
                            st.session_state.selected_vin = None
                            st.rerun()
        
        conn.close()
    
    with tab2:
        st.header("📊 業務人員銷售清單")
        conn = sqlite3.connect('haoyuan.db')
        df_sales = pd.read_sql_query("SELECT * FROM vehicle_master WHERE status='已售'", conn)
        conn.close()
        
        if not df_sales.empty:
            # 篩選器
            col1, col2 = st.columns(2)
            # 業務人員篩選
            if 'sales_person' in df_sales.columns:
                available_sales = sorted(df_sales['sales_person'].dropna().unique().tolist())
                if available_sales:
                    selected_sales = col1.multiselect("業務人員", available_sales, default=available_sales)
                    df_sales = df_sales[df_sales['sales_person'].isin(selected_sales)]
            
            # 日期篩選
            start_date = col2.date_input("開始日期", value=datetime(2024, 1, 1), key="sales_start")
            end_date = col2.date_input("結束日期", value=datetime.now(), key="sales_end")
            if 'out_date' in df_sales.columns:
                df_sales = df_sales[
                    (df_sales['out_date'].notna()) & 
                    (df_sales['out_date'] >= start_date.strftime("%Y-%m-%d")) & 
                    (df_sales['out_date'] <= end_date.strftime("%Y-%m-%d"))
                ]
            
            # 統計資訊
            st.metric("總銷售台數", len(df_sales))
            if 'profit' in df_sales.columns:
                st.metric("總獲利", f"NT$ {df_sales['profit'].sum():,.0f}")
            
            # 顯示清單（包含車輛基本資訊）
            display_cols = ['vin', 'engine', 'v_type', 'vendor', 'model', 'year', 'color', 'cost', 
                           'sales_person', 'plate_no', 'out_date', 'profit', 'cust_name', 'cust_phone']
            available_cols = [col for col in display_cols if col in df_sales.columns]
            st.dataframe(df_sales[available_cols], use_container_width=True)
        else:
            st.info("尚無銷售記錄")
    
    with tab3:
        st.header("✏️ 修改/刪除銷售記錄")
        conn = sqlite3.connect('haoyuan.db')
        df_all_sales = pd.read_sql_query("SELECT * FROM vehicle_master WHERE status='已售'", conn)
        conn.close()
        
        if not df_all_sales.empty:
            # 搜尋功能
            st.subheader("搜尋銷售記錄")
            search_option = st.radio("搜尋方式", ["車身號碼 (VIN)", "引擎號碼"], horizontal=True)
            search_input = st.text_input(f"請輸入{search_option}")
            
            if search_input:
                if search_option == "車身號碼 (VIN)":
                    df_search = df_all_sales[df_all_sales['vin'].str.contains(search_input, case=False, na=False)]
                else:
                    df_search = df_all_sales[df_all_sales['engine'].str.contains(search_input, case=False, na=False)]
                
                if not df_search.empty:
                    if len(df_search) == 1:
                        edit_sale = df_search.iloc[0]
                        edit_vin = edit_sale['vin']
                        
                        # 刪除功能
                        st.write("---")
                        col_del1, col_del2 = st.columns([3, 1])
                        with col_del1:
                            st.info(f"找到車輛：{edit_vin} - {edit_sale.get('model', '')} - {edit_sale.get('plate_no', '')}")
                        with col_del2:
                            if st.button("🗑️ 刪除銷售記錄", key="del_sale_btn_tab3", type="primary"):
                                conn = sqlite3.connect('haoyuan.db')
                                c = conn.cursor()
                                # 將狀態改回待售，並清空銷售相關欄位
                                c.execute("""UPDATE vehicle_master SET status='待售', cust_name=NULL, cust_phone=NULL, 
                                            cust_birthday=NULL, cust_address=NULL, out_date=NULL, plate_no=NULL, inv_out=NULL, 
                                            finance_subsidy=NULL, acc_credit=NULL, profit=NULL, sales_person=NULL,
                                            file_license=NULL, file_invoice=NULL, file_registration=NULL, file_original=NULL 
                                            WHERE vin=?""", (edit_vin,))
                                conn.commit()
                                conn.close()
                                st.success(f"銷售記錄 {edit_vin} 已刪除，車輛狀態已改為待售")
                                st.rerun()
                        
                        # 編輯表單
                        with st.form("edit_sale_form_tab3"):
                            st.write("**修改銷售記錄：**")

                            # 車輛基本資訊（唯讀顯示）

                            st.write("---")
                            st.subheader("車輛基本資訊")
                            col_info1, col_info2, col_info3 = st.columns(3)
                            with col_info1:
                                st.text_input("車身號碼 (VIN)", value=edit_sale.get('vin', ''), disabled=True, key="edit_vin_display")
                                st.text_input("車輛來源", value=edit_sale.get('v_type', ''), disabled=True, key="edit_v_type_display")
                                st.text_input("廠商", value=edit_sale.get('vendor', ''), disabled=True, key="edit_vendor_display")
                            with col_info2:
                                st.text_input("引擎號碼", value=edit_sale.get('engine', ''), disabled=True, key="edit_engine_display")
                                st.text_input("車款", value=edit_sale.get('model', ''), disabled=True, key="edit_model_display")
                                st.text_input("年份", value=edit_sale.get('year', ''), disabled=True, key="edit_year_display")

                            with col_info3:
                                st.text_input("顏色", value=edit_sale.get('color', ''), disabled=True, key="edit_color_display")
                                cost_value = edit_sale.get('cost', 0)
                                st.number_input("成本", value=float(cost_value) if cost_value is not None else 0.0, disabled=True, format="%.0f", key="edit_cost_display")



                            st.write("---")
                            st.subheader("銷售資訊")
                            col_e1, col_e2 = st.columns(2)
                            with col_e1:
                                edit_sales_opts = get_sales_persons()
                                if edit_sales_opts:
                                    edit_sales_person = st.selectbox("業務人員姓名 *", options=[""] + edit_sales_opts, 
                                        index=edit_sales_opts.index(edit_sale.get('sales_person', '')) + 1 if edit_sale.get('sales_person', '') in edit_sales_opts else 0)
                                else:
                                    edit_sales_person = st.text_input("業務人員姓名 *", value=edit_sale.get('sales_person', ''))
                                edit_c_name = st.text_input("顧客姓名", value=edit_sale.get('cust_name', ''))
                                edit_c_phone = st.text_input("顧客電話", value=edit_sale.get('cust_phone', ''))
                            
                            with col_e2:
                                edit_c_bday_str = edit_sale.get('cust_birthday', '')
                                edit_c_bday = st.date_input("顧客生日", value=datetime.strptime(edit_c_bday_str, "%Y-%m-%d").date() if edit_c_bday_str else datetime.now())
                                edit_c_addr = st.text_input("顧客地址", value=edit_sale.get('cust_address', ''))


                            st.write("---")
                            edit_out_date_str = edit_sale.get('out_date', '')
                            edit_out_date = st.date_input("領牌日", value=datetime.strptime(edit_out_date_str, "%Y-%m-%d").date() if edit_out_date_str else datetime.now())
                            edit_out_plate = st.text_input("車牌號碼", value=edit_sale.get('plate_no', ''))
                            edit_out_inv = st.text_input("銷項發票號碼", value=edit_sale.get('inv_out', ''))
                            # 計算原始成交金額：獲利 + 成本 + 分期補貼 + 改裝補貼
                            profit_val = edit_sale.get('profit')
                            cost_val = edit_sale.get('cost')
                            finance_val = edit_sale.get('finance_subsidy')
                            acc_val = edit_sale.get('acc_credit')
                            original_price = (profit_val if profit_val is not None else 0) + (cost_val if cost_val is not None else 0) + (finance_val if finance_val is not None else 0) + (acc_val if acc_val is not None else 0)
                            edit_out_price = st.number_input("成交金額", min_value=0, value=int(original_price) if original_price and original_price > 0 else 0)

                            st.write("---")
                            f_subsidy_value = edit_sale.get('finance_subsidy', 0)
                            edit_f_subsidy = st.number_input("分期補貼息成本", value=float(f_subsidy_value) if f_subsidy_value is not None else 0.0)
                            acc_credit_value = edit_sale.get('acc_credit', 0)
                            edit_acc_credit = st.number_input("贈送改裝金金額", value=float(acc_credit_value) if acc_credit_value is not None else 0.0)

                            # 上傳資料顯示

                            st.write("---")
                            st.subheader("上傳文件")
                            file_preview_col1, file_preview_col2 = st.columns(2)

                            # 文件上傳器
                            edit_file_license = st.file_uploader("📄 重新上傳行照", type=['png', 'jpg', 'jpeg', 'pdf'], key="edit_file_license")
                            edit_file_invoice = st.file_uploader("🧾 重新上傳發票", type=['png', 'jpg', 'jpeg', 'pdf'], key="edit_file_invoice")
                            edit_file_registration = st.file_uploader("📋 重新上傳領牌登記書", type=['png', 'jpg', 'jpeg', 'pdf'], key="edit_file_registration")
                            edit_file_original = st.file_uploader("📎 重新上傳原始資料", type=['png', 'jpg', 'jpeg', 'pdf'], key="edit_file_original")

                            # 構建文件上傳字典
                            edit_file_paths = {
                                'file_license': edit_file_license,
                                'file_invoice': edit_file_invoice,
                                'file_registration': edit_file_registration,
                                'file_original': edit_file_original
                            }

                            # 顯示現有文件
                            st.write("---")
                            st.subheader("現有文件預覽")
                            file_preview_col1, file_preview_col2 = st.columns(2)

                            file_fields = [
                                ('file_license', '📄 行照', file_preview_col1),
                                ('file_invoice', '🧾 發票', file_preview_col1),
                                ('file_registration', '📋 領牌登記書', file_preview_col2),
                                ('file_original', '📎 原始資料', file_preview_col2),
                            ]

                            for file_field, file_label, col in file_fields:
                                with col:
                                    file_path = edit_sale.get(file_field)
                                    if file_path and os.path.exists(file_path):
                                        st.write(f"**{file_label}**")
                                        # 判斷是否為圖片檔案
                                        if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                                            st.image(file_path, caption=file_label, width=200)
                                        else:
                                            st.info(f"檔案：{os.path.basename(file_path)}")
                                        # 如果是 PDF，可以添加下載連結
                                        if file_path.lower().endswith('.pdf'):
                                            with open(file_path, "rb") as pdf_file:
                                                st.download_button(
                                                    label=f"下載 {file_label}",
                                                    data=pdf_file.read(),
                                                    file_name=os.path.basename(file_path),
                                                    mime="application/pdf"
                                                )
                                    else:
                                        st.write(f"**{file_label}**")
                                        st.info("尚未上傳")

                            col_submit1, col_submit2 = st.columns(2)
                            with col_submit1:
                                if st.form_submit_button("💾 儲存修改"):
                                    if edit_sales_person:
                                        # 處理文件上傳（重新上傳替換）
                                        upload_dir = "uploads"
                                        os.makedirs(upload_dir, exist_ok=True)
                                        final_file_paths = {}

                                        file_names_map = {
                                            'file_license': '行照',
                                            'file_invoice': '發票',
                                            'file_registration': '領牌登記書',
                                            'file_original': '原始資料'
                                        }

                                        for file_key, file_obj in edit_file_paths.items():
                                            if file_obj is not None:
                                                # 刪除舊文件
                                                old_path = edit_sale.get(file_key)
                                                if old_path and os.path.exists(old_path):
                                                    try:
                                                        os.remove(old_path)
                                                    except:
                                                        pass

                                                # 保存新文件
                                                file_ext = os.path.splitext(file_obj.name)[1]
                                                save_filename = f"{edit_vin}_{file_names_map[file_key]}{file_ext}"
                                                save_path = os.path.join(upload_dir, save_filename)
                                                with open(save_path, "wb") as f:
                                                    f.write(file_obj.getbuffer())
                                                final_file_paths[file_key] = save_path
                                            else:
                                                # 保留舊文件路徑
                                                final_file_paths[file_key] = edit_sale.get(file_key)

                                        conn = sqlite3.connect('haoyuan.db')
                                        c = conn.cursor()
                                        # 重新計算獲利（成交金額 - 成本 - 分期補貼 - 改裝補貼）
                                        car_cost = edit_sale.get('cost', 0)
                                        edit_net_profit = edit_out_price - car_cost - edit_f_subsidy - edit_acc_credit
                                        c.execute("""UPDATE vehicle_master SET cust_name=?, cust_phone=?, cust_birthday=?, cust_address=?, 
                                                 out_date=?, plate_no=?, inv_out=?, finance_subsidy=?, acc_credit=?, profit=?, sales_person=?,
                                                 file_license=?, file_invoice=?, file_registration=?, file_original=?
                                                 WHERE vin=?""", 
                                                 (edit_c_name, edit_c_phone, edit_c_bday.strftime("%Y-%m-%d"), edit_c_addr, 
                                                  edit_out_date.strftime("%Y-%m-%d"), edit_out_plate, edit_out_inv, 
                                                  edit_f_subsidy, edit_acc_credit, edit_net_profit, edit_sales_person,
                                                  final_file_paths.get('file_license'), final_file_paths.get('file_invoice'), 
                                                  final_file_paths.get('file_registration'), final_file_paths.get('file_original'),
                                                  edit_vin))

                                        conn.commit()
                                        conn.close()
                                        st.success("修改完成")
                                        st.rerun()
                                    else:
                                        st.error("請輸入業務人員姓名")
                            with col_submit2:
                                if st.form_submit_button("❌ 取消"):
                                    st.rerun()
        else:
            st.info("尚無銷售記錄")

# --- 8. 系統設定（管理廠商和業務）---
elif menu == "⚙️ 系統設定":
    tab1, tab2 = st.tabs(["🏭 廠商管理", "👤 業務管理"])
    
    with tab1:
        st.header("🏭 廠商管理")
        
        # 顯示現有廠商
        st.subheader("現有廠商")
        conn = sqlite3.connect('haoyuan.db')
        df_vendors = pd.read_sql_query("SELECT value FROM base_options WHERE type='廠商'", conn)
        conn.close()
        if not df_vendors.empty:
            st.dataframe(df_vendors, use_container_width=True)
        else:
            st.info("尚無廠商，請使用下方表單新增")
        
        st.write("---")
        with st.form("vendor_form"):
            vendor_val = st.text_input("廠商名稱 (例：Yamaha、台鈴)")
            if st.form_submit_button("新增廠商"):
                if vendor_val:
                    conn = sqlite3.connect('haoyuan.db')
                    conn.execute("INSERT OR IGNORE INTO base_options VALUES (?, ?)", ("廠商", vendor_val))
                    conn.commit()
                    conn.close()
                    st.success(f"已新增廠商：{vendor_val}")
                    st.rerun()
                else:
                    st.error("請輸入廠商名稱")
        
        # 刪除廠商功能
        st.write("---")
        st.subheader("刪除廠商")
        if not df_vendors.empty:
            with st.form("del_vendor_form"):
                del_vendor = st.selectbox("選擇要刪除的廠商", df_vendors['value'].tolist())
                if st.form_submit_button("刪除廠商"):
                    conn = sqlite3.connect('haoyuan.db')
                    conn.execute("DELETE FROM base_options WHERE type='廠商' AND value=?", (del_vendor,))
                    conn.commit()
                    conn.close()
                    st.success(f"已刪除廠商：{del_vendor}")
                    st.rerun()
    
    with tab2:
        st.header("👤 業務管理")
        
        # 顯示現有業務
        st.subheader("現有業務")
        conn = sqlite3.connect('haoyuan.db')
        df_sales = pd.read_sql_query("SELECT value FROM base_options WHERE type='業務'", conn)
        conn.close()
        if not df_sales.empty:
            st.dataframe(df_sales, use_container_width=True)
        else:
            st.info("尚無業務，請使用下方表單新增")
        
        st.write("---")
        with st.form("sales_form"):
            sales_val = st.text_input("業務姓名 (例：張三、李四)")
            if st.form_submit_button("新增業務"):
                if sales_val:
                    conn = sqlite3.connect('haoyuan.db')
                    conn.execute("INSERT OR IGNORE INTO base_options VALUES (?, ?)", ("業務", sales_val))
                    conn.commit()
                    conn.close()
                    st.success(f"已新增業務：{sales_val}")
                    st.rerun()
                else:
                    st.error("請輸入業務姓名")
        
        # 刪除業務功能
        st.write("---")
        st.subheader("刪除業務")
        if not df_sales.empty:
            with st.form("del_sales_form"):
                del_sales = st.selectbox("選擇要刪除的業務", df_sales['value'].tolist())
                if st.form_submit_button("刪除業務"):
                    conn = sqlite3.connect('haoyuan.db')
                    conn.execute("DELETE FROM base_options WHERE type='業務' AND value=?", (del_sales,))
                    conn.commit()
                    conn.close()
                    st.success(f"已刪除業務：{del_sales}")
                    st.rerun()