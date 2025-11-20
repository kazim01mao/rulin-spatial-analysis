import streamlit as st
import pandas as pd
import pydeck as pdk
import networkx as nx
import matplotlib.pyplot as plt
import os

# ================= 0. 路径配置 =================
# 云端部署时，数据文件就在当前目录下，或者使用相对路径

# 获取当前脚本(rulin.py)所在的目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 设定数据路径为当前目录 (假设你把CSV和py放在一起)
DATA_DIR = CURRENT_DIR 
# 或者如果你的CSV在同级的 'Result files' 文件夹里，就写: os.path.join(CURRENT_DIR, 'Result files')

# 输出路径 (云端通常不可写，或者只能写临时目录，这里为了不报错可以设为临时目录)
OUTPUT_DIR = CURRENT_DIR

# ================= 1. 页面配置 =================
st.set_page_config(page_title="儒林外史 GIS 分析系统", layout="wide")
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'Heiti TC', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False


# ================= 2. 数据加载与清洗 (修复版) =================
@st.cache_data
def load_data():
    try:
        # 1. 读取文件
        places = pd.read_csv(os.path.join(DATA_DIR, 'places.csv'), encoding='utf-8-sig')
        freq_chapter = pd.read_csv(os.path.join(DATA_DIR, 'place_freq.csv'), encoding='utf-8-sig')
        # 注意：我们不再严重依赖 freq_summary.csv 的数据列，只用它来做校验或辅助，主要数据靠算
        context = pd.read_csv(os.path.join(DATA_DIR, 'place_analysis_ch01-20_cha_act.csv'), encoding='utf-8-sig')
        
        # 2. 清洗列名 (去除看不见的空格)
        for df in [places, freq_chapter, context]:
            df.columns = df.columns.str.strip()

        # 3. 核心修复：直接从分章节数据计算总览数据
        # 这样可以保证 'per_1k_chars' 肯定有值，而且和分章节数据完全对得上
        # 我们对 'count' 求和，对 'per_1k_chars' 也求和 (代表累积关注度)
        freq_total = freq_chapter.groupby('place', as_index=False)[['count', 'per_1k_chars']].sum()
        
        # 4. 地理编码合并 (给数据加上经纬度)
        # 给分章节表加坐标
        freq_chapter = freq_chapter.merge(places, on='place', how='left')
        # 给我们刚算出来的总表加坐标
        freq_total = freq_total.merge(places, on='place', how='left')
        # 给语境表加坐标
        context = context.merge(places, on='place', how='left')

        return places, freq_chapter, freq_total, context, None
    except Exception as e:
        return None, None, None, None, str(e)

df_places, df_freq_chapter, df_freq_total, df_context, error_msg = load_data()

if error_msg:
    st.error(f"❌ 数据加载错误: {error_msg}")
    st.stop()

# ================= 3. 侧边栏 =================
st.sidebar.title("🗺️ 儒林 GIS 控制台")
analysis_mode = st.sidebar.radio(
    "选择分析模块:",
    ["1. GIS 地理空间分析", "2. 人物-空间网络分析", "3. 文本深描与活动查询"]
)
st.sidebar.markdown("---")
st.sidebar.info(f"数据范围: 第1-20回\n地点总数: {len(df_places)}")

# ================= 4. 主界面逻辑 =================
st.title("🏛️ 《儒林外史》空间叙事分析系统")

# --------------------------------------------------------
# 模块 1: GIS 地理空间分析 (交互升级版)
# --------------------------------------------------------
if analysis_mode == "1. GIS 地理空间分析":
    st.header("📍 空间分布与热度演变")
    
    col_ctrl, col_map = st.columns([1, 3])
    
    with col_ctrl:
        st.subheader("图层控制")
        view_mode = st.radio("时间维度", ["全书总览 (Total)", "分回演变 (Timeline)"])
        
        map_data = pd.DataFrame()
        display_radius = 5000
        
        if view_mode == "全书总览 (Total)":
            map_data = df_freq_total.copy()
            map_data = map_data.dropna(subset=['lat', 'lon'])
            display_radius = 10000
            st.metric("总活跃地点", len(map_data))
            if not map_data.empty:
                top_place = map_data.loc[map_data['count'].idxmax()]
                st.metric("最热地点", f"{top_place['place']}", f"{int(top_place['count'])}次")
            
        else:
            # === 改进点：智能时间轴 ===
            
            # 1. 计算哪些章节有数据 (Valid Chapters)
            # 这里的逻辑是：只有 count > 0 的章节才被视为有效
            chap_summary = df_freq_chapter.groupby('chapter')['count'].sum().reset_index()
            valid_chapters = chap_summary[chap_summary['count'] > 0]['chapter'].unique()
            valid_chapters = sorted(valid_chapters) # 排序
            
            # 2. 显示一个小柱状图，让用户直观看到哪些章节是“空的”
            st.markdown("**📊 章节热度概览 (Gap View)**")
            st.markdown("<small style='color:gray'>柱子高度代表地点提及次数，缺失柱子即为无数据。</small>", unsafe_allow_html=True)
            st.bar_chart(chap_summary.set_index('chapter')['count'], height=100, color="#FF4B4B")
            
            # 3. 使用 select_slider 实现“跳跃式”选择
            if len(valid_chapters) > 0:
                selected_chap = st.select_slider(
                    "👉 拖动选择章节 (自动跳过无数据章节):",
                    options=valid_chapters,
                    value=valid_chapters[0] # 默认选第一个有数据的
                )
                
                # 筛选数据
                map_data = df_freq_chapter[df_freq_chapter['chapter'] == selected_chap].copy()
                map_data = map_data.dropna(subset=['lat', 'lon'])
                map_data = map_data[map_data['count'] > 0]
                display_radius = 15000
                
                st.success(f"📅 当前展示：**第 {selected_chap} 回**")
                if not map_data.empty:
                    top_in_chap = map_data.loc[map_data['count'].idxmax()]
                    st.info(f"核心地点: **{top_in_chap['place']}** ({int(top_in_chap['count'])}次)")
            else:
                st.error("数据集中没有任何章节包含有效地点数据。")

        show_labels = st.checkbox("显示地名标签", value=True)

    with col_map:
        if not map_data.empty:
            # --- 地图图层 ---
            layers_list = []
            
            # 1. 气泡
            scatter_layer = pdk.Layer(
                "ScatterplotLayer",
                map_data,
                get_position='[lon, lat]',
                get_color='[200, 30, 0, 180]',
                get_radius='count',
                radius_scale=display_radius,
                radius_min_pixels=8, # 稍微调大一点，更好点选
                radius_max_pixels=60,
                pickable=True,
                auto_highlight=True,
            )
            layers_list.append(scatter_layer)

            # 2. 标签
            if show_labels:
                text_layer = pdk.Layer(
                    "TextLayer",
                    map_data,
                    get_position='[lon, lat]',
                    get_text='place',
                    get_color=[0, 0, 0, 200],
                    get_size=15,
                    get_alignment_baseline="'bottom'",
                    get_text_anchor="'middle'",
                    pixel_offset=[0, -15]
                )
                layers_list.append(text_layer)

            # 3. 渲染
            view_state = pdk.ViewState(
                latitude=map_data['lat'].mean(),
                longitude=map_data['lon'].mean(),
                zoom=6,
                pitch=0,
            )

            st.pydeck_chart(pdk.Deck(
                map_style=pdk.map_styles.CARTO_LIGHT, 
                initial_view_state=view_state,
                layers=layers_list,
                tooltip={
                    "html": "<b>{place}</b><br/>频次: <b>{count}</b>",
                    "style": {"backgroundColor": "steelblue", "color": "white"}
                }
            ))
            
            # 数据表
            with st.expander("🔍 查看底层数据 (Data Table)", expanded=True):
                cols_to_show = ['place', 'count', 'lat', 'lon']
                if 'per_1k_chars' in map_data.columns:
                    cols_to_show.insert(2, 'per_1k_chars')
                st.dataframe(map_data[cols_to_show].sort_values('count', ascending=False), use_container_width=True)
        else:
            st.warning("⚠️ 当前视图无数据。")

# --------------------------------------------------------
# 模块 2: 人物-空间网络分析
# --------------------------------------------------------
elif analysis_mode == "2. 人物-空间网络分析":
    st.header("🕸️ 人物轨迹与地点关联网络")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        G = nx.Graph()
        valid_links = df_context.dropna(subset=['Character1', 'place'])
        
        for _, row in valid_links.iterrows():
            char1 = str(row['Character1']).strip()
            place = str(row['place']).strip()
            if char1 and place and char1 != 'nan':
                G.add_edge(char1, place, type='visited')
            if pd.notna(row['Character2']):
                char2 = str(row['Character2']).strip()
                if char2 and char2 != 'nan':
                    G.add_edge(char2, place, type='visited')

        if len(G.nodes) > 0:
            fig, ax = plt.subplots(figsize=(12, 8))
            pos = nx.spring_layout(G, k=0.5, seed=42)
            places_list = df_places['place'].unique().tolist()
            node_colors = ['#1f78b4' if n in places_list else '#ff7f0e' for n in G.nodes()]
            node_sizes = [1000 if n in places_list else 500 for n in G.nodes()]

            nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=node_colors, alpha=0.9)
            nx.draw_networkx_edges(G, pos, alpha=0.3, edge_color='gray')
            nx.draw_networkx_labels(G, pos, font_family='sans-serif', font_size=10)
            plt.axis('off')
            st.pyplot(fig)
        else:
            st.error("无法生成网络图。")

    with col2:
        st.info("🔵 蓝色 = 地点\n🟠 橙色 = 人物")

# --------------------------------------------------------
# 模块 3: 文本深描
# --------------------------------------------------------
elif analysis_mode == "3. 文本深描与活动查询":
    st.header("📖 活动分类查询")
    
    col_filter, col_table = st.columns([1, 3])
    with col_filter:
        sel_place = st.selectbox("选择地点", ["全部"] + list(df_places['place']))
        temp_df = df_context.copy()
        if sel_place != "全部":
            temp_df = temp_df[temp_df['place'] == sel_place]
        avail_chars = list(set(temp_df['Character1'].dropna().unique()))
        sel_char = st.selectbox("选择人物", ["全部"] + avail_chars)
        if sel_char != "全部":
            temp_df = temp_df[temp_df['Character1'] == sel_char]

    with col_table:
        st.dataframe(temp_df[['chapter', 'place', 'Character1', 'Activity', 'snippet']], use_container_width=True)
        if st.button("导出结果"):
            temp_df.to_csv(os.path.join(OUTPUT_DIR, 'filtered_result.csv'), index=False, encoding='utf-8-sig')
            st.success("已导出！")