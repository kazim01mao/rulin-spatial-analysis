import streamlit as st
import pandas as pd
import pydeck as pdk
import networkx as nx
import matplotlib.pyplot as plt
import os

# ================= 0. Path Configuration =================
# Relative path for Cloud Deployment
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = CURRENT_DIR
OUTPUT_DIR = os.path.join(CURRENT_DIR, 'output')

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# ================= 1. Page Config & Styling =================
st.set_page_config(
    page_title="The Scholars Spatial Analysis",
    page_icon="📜",
    layout="wide"
)

# Matplotlib Font Settings (Keep Chinese support for data visualization)
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'Heiti TC', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

# Custom CSS for Responsiveness and Styling
st.markdown("""
    <style>
    /* Responsive Title using clamp() */
    .main-title {
        font-family: 'Georgia', serif;
        color: #8B0000; /* Classic Red */
        font-weight: bold;
        text-align: center;
        /* Minimum 24px, Preferred 4vw, Maximum 50px */
        font-size: clamp(24px, 4vw, 50px); 
        margin-bottom: 10px;
        padding-top: 10px;
    }
    .sub-title {
        font-family: 'Arial', sans-serif;
        color: #555;
        text-align: center;
        font-size: clamp(14px, 1.5vw, 20px);
        font-style: italic;
        margin-bottom: 30px;
    }
    .highlight {
        color: #8B0000;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# ================= 2. Data Loading =================
@st.cache_data
def load_data():
    try:
        # Load CSVs
        places = pd.read_csv(os.path.join(DATA_DIR, 'places.csv'), encoding='utf-8-sig')
        freq_chapter = pd.read_csv(os.path.join(DATA_DIR, 'place_freq.csv'), encoding='utf-8-sig')
        context = pd.read_csv(os.path.join(DATA_DIR, 'place_analysis_ch01-20_cha_act.csv'), encoding='utf-8-sig')
        
        # Clean Columns
        for df in [places, freq_chapter, context]:
            df.columns = df.columns.str.strip()

        # Calculate Total Frequency dynamically
        freq_total = freq_chapter.groupby('place', as_index=False)[['count', 'per_1k_chars']].sum()
        
        # Geocoding Merge
        freq_chapter = freq_chapter.merge(places, on='place', how='left')
        freq_total = freq_total.merge(places, on='place', how='left')
        context = context.merge(places, on='place', how='left')

        return places, freq_chapter, freq_total, context, None
    except Exception as e:
        return None, None, None, None, str(e)

df_places, df_freq_chapter, df_freq_total, df_context, error_msg = load_data()

if error_msg:
    st.error(f"❌ Data Loading Error: {error_msg}")
    st.stop()

# ================= 3. Sidebar =================
with st.sidebar:
    # Updated: Use local image for stability
    # Make sure you have 'cover.jpg' in the same folder!
    image_path = os.path.join(CURRENT_DIR, 'cover.jpg')
    
    if os.path.exists(image_path):
        st.image(image_path, caption="The Scholars (儒林外史)", use_container_width=True)
    else:
        # Fallback if image is missing
        st.markdown("### 📜 The Scholars")
    
    st.header("🎛️ Navigation")
    analysis_mode = st.radio(
        "Select Module:",
        [
            "1. GIS Spatial Analysis", 
            "2. Network Analysis", 
            "3. Close Reading"
        ]
    )
    
    st.markdown("---")
    with st.expander("ℹ️ About Project"):
        st.markdown("""
        **Course**: Digital Humanities  
        **Scope**: Chapters 1-20  
        **Tech**: Python, Streamlit, PyDeck  
        **Author**: Junyu Mao
        """)

# ================= 4. Main Interface =================

# Main Title (Responsive)
st.markdown('<div class="main-title">Mapping the Literati:<br>A Spatial Analysis of The Scholars (Ch 1-20)</div>', unsafe_allow_html=True)

# --------------------------------------------------------
# Module 1: GIS Spatial Analysis
# --------------------------------------------------------
if analysis_mode == "1. GIS Spatial Analysis":
    st.markdown("### 📍 Spatial Distribution & Evolution")
    st.caption("Visualizing the geographical hotspots and their temporal shifts.")
    
    col_ctrl, col_map = st.columns([1, 2.5])
    
    with col_ctrl:
        st.subheader("⚙️ Controls")
        view_mode = st.radio(
            "Dimension:", 
            ["Total Overview", "Chapter Timeline"]
        )
        
        map_data = pd.DataFrame()
        display_radius = 5000
        
        if view_mode == "Total Overview":
            map_data = df_freq_total.copy()
            map_data = map_data.dropna(subset=['lat', 'lon'])
            display_radius = 10000
            
            # Metrics
            c1, c2 = st.columns(2)
            c1.metric("Total Locations", len(map_data))
            if not map_data.empty:
                top_place = map_data.loc[map_data['count'].idxmax()]
                c2.metric("Top Hub", top_place['place'])
            
        else:
            # Timeline Logic
            chap_summary = df_freq_chapter.groupby('chapter')['count'].sum().reset_index()
            valid_chapters = sorted(chap_summary[chap_summary['count'] > 0]['chapter'].unique())
            
            st.markdown("##### 📅 Chapter Activity Heatmap")
            st.bar_chart(chap_summary.set_index('chapter')['count'], height=100, color="#8B0000")
            
            if len(valid_chapters) > 0:
                selected_chap = st.select_slider(
                    "Select Chapter (Jump to active ones):",
                    options=valid_chapters,
                    value=valid_chapters[0]
                )
                
                map_data = df_freq_chapter[df_freq_chapter['chapter'] == selected_chap].copy()
                map_data = map_data[map_data['count'] > 0].dropna(subset=['lat', 'lon'])
                display_radius = 15000
                
                if not map_data.empty:
                    top_in_chap = map_data.loc[map_data['count'].idxmax()]
                    st.success(f"🚩 **Ch {selected_chap} Center**: {top_in_chap['place']}")
            else:
                st.warning("No spatial data available for specific chapters.")

        show_labels = st.toggle("Show Labels", value=True)

    with col_map:
        if not map_data.empty:
            # PyDeck Layer
            layers = [
                pdk.Layer(
                    "ScatterplotLayer",
                    map_data,
                    get_position='[lon, lat]',
                    get_color='[139, 0, 0, 180]', # Deep Red
                    get_radius='count',
                    radius_scale=display_radius,
                    radius_min_pixels=5,
                    radius_max_pixels=50,
                    pickable=True,
                    auto_highlight=True,
                )
            ]
            
            if show_labels:
                layers.append(pdk.Layer(
                    "TextLayer",
                    map_data,
                    get_position='[lon, lat]',
                    get_text='place',
                    get_color=[0, 0, 0, 200],
                    get_size=14,
                    get_alignment_baseline="'bottom'",
                    get_text_anchor="'middle'",
                    pixel_offset=[0, -12]
                ))

            view_state = pdk.ViewState(
                latitude=map_data['lat'].mean(),
                longitude=map_data['lon'].mean(),
                zoom=5.8,
                pitch=0
            )

            st.pydeck_chart(pdk.Deck(
                map_style=pdk.map_styles.CARTO_LIGHT,
                initial_view_state=view_state,
                layers=layers,
                tooltip={"html": "<b>{place}</b><br/>Freq: {count}", "style": {"backgroundColor": "#8B0000", "color": "white"}}
            ))
            
            with st.expander("📊 View Raw Data Table"):
                # Updated parameter: use_container_width
                st.dataframe(map_data[['place', 'count', 'per_1k_chars', 'lat', 'lon']].sort_values('count', ascending=False), use_container_width=True)
        else:
            st.info("Please select another chapter.")

# --------------------------------------------------------
# Module 2: Network Analysis
# --------------------------------------------------------
elif analysis_mode == "2. Network Analysis":
    st.markdown("### 🕸️ Character-Place Network")
    st.caption("Visualizing the mobility and social connections between characters and places.")

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
            fig, ax = plt.subplots(figsize=(10, 7))
            pos = nx.spring_layout(G, k=0.6, seed=42)
            
            places_list = df_places['place'].unique().tolist()
            node_colors = ['#4682B4' if n in places_list else '#FF6347' for n in G.nodes()] # SteelBlue & Tomato
            node_sizes = [900 if n in places_list else 500 for n in G.nodes()]

            nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=node_colors, alpha=0.9, ax=ax)
            nx.draw_networkx_edges(G, pos, alpha=0.3, edge_color='gray', ax=ax)
            nx.draw_networkx_labels(G, pos, font_family='sans-serif', font_size=9, ax=ax)
            
            ax.axis('off')
            st.pyplot(fig)
        else:
            st.error("Not enough data to build network.")

    with col2:
        st.markdown("#### 🏷️ Legend")
        st.markdown("🔵 **Place (地点)**\n\nNarrative locations.")
        st.markdown("🟠 **Character (人物)**\n\nAgents moving across space.")
        
        st.info("**Insight**: \n\nCharacters like **Kuang Chaoren (匡超人)** connect multiple regions, indicating high social mobility.")

# --------------------------------------------------------
# Module 3: Close Reading
# --------------------------------------------------------
elif analysis_mode == "3. Close Reading":
    st.markdown("### 📖 Textual Context & Activities")
    st.caption("Filter original text snippets by place or character.")
    
    col_filter, col_data = st.columns([1, 3])
    
    with col_filter:
        st.markdown("#### 🔍 Filters")
        sel_place = st.selectbox("Place", ["All"] + list(df_places['place']))
        
        temp_df = df_context.copy()
        if sel_place != "All":
            temp_df = temp_df[temp_df['place'] == sel_place]
            
        avail_chars = sorted(list(set(temp_df['Character1'].dropna().unique())))
        sel_char = st.selectbox("Character", ["All"] + avail_chars)
        
        if sel_char != "All":
            temp_df = temp_df[temp_df['Character1'] == sel_char]
            
        st.metric("Snippets Found", len(temp_df))

    with col_data:
        # Updated parameter: use_container_width
        st.dataframe(
            temp_df[['chapter', 'place', 'Character1', 'Activity', 'snippet']],
            use_container_width=True,
            height=500,
            column_config={
                "chapter": st.column_config.NumberColumn("Ch.", format="%d", width="small"),
                "snippet": st.column_config.TextColumn("Original Text (原文)", width="large"),
                "Activity": st.column_config.TextColumn("Activity Type", width="medium"),
                "Character1": "Character"
            }
        )
        
        # Download Button
        csv = temp_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="📥 Download Filtered Data",
            data=csv,
            file_name=f"filtered_context.csv",
            mime="text/csv",
        )

# ================= Footer =================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray; font-size: 0.8em;'>"
    "Assignment 2: Digital Humanities Project | Created with Streamlit & Python"
    "</div>", 
    unsafe_allow_html=True
)