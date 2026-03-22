# from __future__ import annotations
# import sys, os
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# import streamlit as st
# from dotenv import load_dotenv
# load_dotenv()

# st.set_page_config(
#     page_title="Engram",
#     page_icon="🧠",
#     layout="wide",
#     initial_sidebar_state="expanded",
# )

# st.markdown("""
# <style>
#   .block-container { padding-top: 1.5rem; }
#   .metric-label { font-size: 12px; }
#   .stAlert { border-radius: 8px; }
#   div[data-testid="stSidebarContent"] { padding-top: 1rem; }
# </style>
# """, unsafe_allow_html=True)


# # ── Lazy init — cached so modules load once ──────────────────────────────────

# @st.cache_resource
# def get_engine():
#     from ingestion.engine import IngestionEngine
#     return IngestionEngine()

# @st.cache_resource
# def get_search():
#     from search.search_engine import SearchEngine
#     return SearchEngine()

# @st.cache_resource
# def get_rag():
#     from rag.rag_pipeline import RAGPipeline
#     return RAGPipeline()

# @st.cache_resource
# def get_recommender():
#     from recommendations.recommender import Recommender
#     return Recommender()

# @st.cache_resource
# def get_agent():
#     from agents.monitor_agent import MonitorAgent
#     return MonitorAgent()

# @st.cache_resource
# def get_endee():
#     from utils.endee_client import EndeeClient
#     return EndeeClient()

# @st.cache_resource
# def init_indexes():
#     from core.indexes import initialise_indexes
#     return initialise_indexes()


# # ── Helper — get real vector counts directly from Endee raw API ──────────────
# def _get_real_counts() -> dict:
#     """
#     Reads total_elements directly from Endee's raw list_indexes response.
#     We bypass our wrapper because total_elements updates after upsert
#     but only reflects in the raw SDK call, not in cached wrappers.
#     """
#     try:
#         from endee import Endee
#         c   = Endee()
#         raw = c.list_indexes()
#         # Endee returns {"indexes": [...]}
#         index_list = raw.get("indexes", []) if isinstance(raw, dict) else raw
#         return {
#             idx.get("name", ""): idx.get("total_elements", 0)
#             for idx in index_list
#             if isinstance(idx, dict)
#         }
#     except Exception:
#         return {}


# # ── Initialise indexes on startup ────────────────────────────────────────────
# try:
#     init_indexes()
#     endee_ok = True
# except Exception as e:
#     endee_ok = False
#     st.error(f"Cannot connect to Endee: {e}. Make sure Docker is running.")


# # ── Sidebar ──────────────────────────────────────────────────────────────────
# with st.sidebar:
#     st.markdown("## 🧠 Engram")
#     st.caption("Your personal AI second brain")
#     st.divider()

#     page = st.radio(
#         "Navigate",
#         ["🔍 Search", "💬 Ask AI", "📤 Upload", "🌐 Related", "🤖 Agent", "📊 Stats"],
#         label_visibility="collapsed",
#     )

#     st.divider()

#     # Endee status
#     if endee_ok:
#         st.success("Endee connected ✓")
#     else:
#         st.error("Endee offline ✗")

#     # Sidebar memory count — use real counts
#     try:
#         counts = _get_real_counts()
#         total  = sum(counts.values())
#         st.metric("Total memories", total)
#     except Exception:
#         st.metric("Total memories", "—")


# # ════════════════════════════════════════════════════════════════════════════
# # Page 1 — Search
# # ════════════════════════════════════════════════════════════════════════════
# if page == "🔍 Search":
#     st.title("🔍 Search your memory")
#     st.caption("Semantic search — finds meaning, not just keywords")

#     query = st.text_input(
#         "What are you looking for?",
#         placeholder="e.g. CAP theorem, meeting with Rahul, machine learning notes...",
#     )

#     col1, col2, col3 = st.columns(3)
#     with col1:
#         file_type = st.selectbox(
#             "File type", ["All", "pdf", "text", "markdown", "csv", "docx"]
#         )
#     with col2:
#         top_k = st.slider("Results", 3, 20, 8)
#     with col3:
#         since_days = st.selectbox("Time range", ["All time", "7 days", "30 days", "90 days"])

#     days_map = {"All time": None, "7 days": 7, "30 days": 30, "90 days": 90}
#     days_val = days_map[since_days]
#     ft_val   = None if file_type == "All" else file_type

#     if query:
#         with st.spinner("Searching Endee..."):
#             try:
#                 search  = get_search()
#                 results = search.search(
#                     query,
#                     top_k=top_k,
#                     file_type=ft_val,
#                     since_days=days_val,
#                 )
#             except Exception as e:
#                 st.error(f"Search failed: {e}")
#                 results = []

#         if results:
#             st.success(f"Found {len(results)} memories")
#             for r in results:
#                 with st.expander(
#                     f"**{r.chunk.source_file}** — score: {r.score:.3f}",
#                     expanded=r.rank == 1,
#                 ):
#                     st.markdown(r.snippet)
#                     col_a, col_b, col_c = st.columns(3)
#                     col_a.caption(f"Type: {r.chunk.file_type.value}")
#                     col_b.caption(f"Chunk: {r.chunk.chunk_index + 1}/{r.chunk.total_chunks}")
#                     col_c.caption(f"Words: {r.chunk.word_count}")
#         else:
#             st.info("No results found. Try a different query or upload some files first.")


# # ════════════════════════════════════════════════════════════════════════════
# # Page 2 — Ask AI (RAG)
# # ════════════════════════════════════════════════════════════════════════════
# elif page == "💬 Ask AI":
#     st.title("💬 Ask your documents")
#     st.caption("RAG — answers grounded in YOUR uploaded files")

#     question = st.text_input(
#         "Ask anything about your documents",
#         placeholder="e.g. What did I decide about my career in January? What is CAP theorem?",
#     )

#     top_k_rag = st.slider("Chunks to retrieve from Endee", 3, 10, 5)

#     if question:
#         with st.spinner("Retrieving from Endee + generating answer..."):
#             try:
#                 rag      = get_rag()
#                 response = rag.query(question, top_k=top_k_rag)
#             except Exception as e:
#                 st.error(f"RAG failed: {e}")
#                 response = None

#         if response:
#             st.markdown("### Answer")
#             st.info(response.answer)

#             col1, col2, col3 = st.columns(3)
#             col1.metric("Retrieval", f"{response.retrieval_time_ms}ms")
#             col2.metric("Generation", f"{response.generation_time_ms}ms")
#             col3.metric("Chunks used", response.chunk_count)

#             if response.sources:
#                 st.markdown("### Sources from Endee")
#                 for i, src in enumerate(response.sources, 1):
#                     with st.expander(
#                         f"[{i}] {src.get('source_file', 'unknown')} — score: {src.get('score', 0):.3f}"
#                     ):
#                         st.caption(src.get("content", "")[:300])


# # ════════════════════════════════════════════════════════════════════════════
# # Page 3 — Upload
# # ════════════════════════════════════════════════════════════════════════════
# elif page == "📤 Upload":
#     st.title("📤 Upload documents")
#     st.caption("Supports PDF, TXT, MD, CSV, DOCX")

#     uploaded = st.file_uploader(
#         "Drop files here",
#         type=["pdf", "txt", "md", "csv", "docx"],
#         accept_multiple_files=True,
#     )

#     extract_entities = st.checkbox("Extract entities (needs Groq key)", value=True)

#     if uploaded and st.button("Ingest into Endee", type="primary"):
#         engine = get_engine()
#         for f in uploaded:
#             with st.spinner(f"Processing {f.name}..."):
#                 try:
#                     result = engine.ingest_bytes(
#                         f.read(), f.name,
#                         extract_entities=extract_entities,
#                     )
#                     if result.success:
#                         st.success(
#                             f"✅ **{f.name}** — "
#                             f"{result.chunks_stored} chunks stored, "
#                             f"{result.duplicates_skipped} duplicates skipped, "
#                             f"{result.entities_extracted} entities, "
#                             f"{result.processing_time_ms}ms"
#                         )
#                     else:
#                         st.error(f"❌ {f.name}: {result.errors}")
#                 except Exception as e:
#                     st.error(f"❌ {f.name}: {e}")


# # ════════════════════════════════════════════════════════════════════════════
# # Page 4 — Related Memories
# # ════════════════════════════════════════════════════════════════════════════
# elif page == "🌐 Related":
#     st.title("🌐 Related memories")
#     st.caption("Find how a topic connects across all your documents")

#     topic = st.text_input(
#         "Enter a topic",
#         placeholder="e.g. system design, machine learning, career...",
#     )

#     if topic:
#         with st.spinner("Finding connections in Endee..."):
#             try:
#                 rec         = get_recommender()
#                 connections = rec.find_cross_file_connections(topic, top_k=6)
#                 forgotten   = rec.find_forgotten(query=topic, days=30, top_k=3)
#             except Exception as e:
#                 st.error(f"Failed: {e}")
#                 connections = {}
#                 forgotten   = []

#         if connections:
#             st.markdown(f"### Topic appears in {len(connections)} files")
#             for source, results in connections.items():
#                 with st.expander(f"📄 {source}"):
#                     for r in results:
#                         st.markdown(f"> {r.snippet}")
#                         st.caption(f"Similarity: {r.score:.3f}")
#         else:
#             st.info("No connections found. Upload more files to see cross-document connections.")

#         if forgotten:
#             st.divider()
#             st.markdown("### 💤 You forgot about these")
#             st.caption("Related memories you have not seen in 30+ days")
#             for r in forgotten:
#                 with st.expander(f"📄 {r.chunk.source_file}"):
#                     st.markdown(r.snippet)


# # ════════════════════════════════════════════════════════════════════════════
# # Page 5 — Agent
# # ════════════════════════════════════════════════════════════════════════════
# elif page == "🤖 Agent":
#     st.title("🤖 AI Agent")
#     st.caption("Autonomously scans your memory and generates insights")

#     st.info(
#         "The agent reads all your documents from Endee and finds: "
#         "recurring patterns, contradictions, knowledge gaps, and forgotten memories."
#     )

#     if st.button("Run Agent Now", type="primary"):
#         with st.spinner("Agent scanning your Endee memory..."):
#             try:
#                 agent  = get_agent()
#                 report = agent.run()
#             except Exception as e:
#                 st.error(f"Agent failed: {e}")
#                 report = None

#         if report:
#             st.success(f"Agent run {report.run_id} complete in {report.duration_seconds}s")
#             st.markdown(f"**Summary:** {report.summary}")

#             col1, col2, col3, col4 = st.columns(4)
#             col1.metric("Patterns", report.patterns_found)
#             col2.metric("Contradictions", report.contradictions_found)
#             col3.metric("Gaps", report.gaps_found)
#             col4.metric("Forgotten", report.forgotten_found)

#     st.divider()
#     st.markdown("### Past insights from Endee")

#     try:
#         rec      = get_recommender()
#         insights = rec.get_recent_insights(top_k=10)
#         if insights:
#             for ins in insights:
#                 itype = ins.get("insight_type", "pattern")
#                 color = {
#                     "pattern":          "🔵",
#                     "contradiction":    "🔴",
#                     "knowledge_gap":    "🟡",
#                     "forgotten_memory": "⚪",
#                 }.get(itype, "⚪")
#                 with st.expander(f"{color} {ins.get('title', 'Insight')}"):
#                     st.markdown(ins.get("description", ""))
#                     st.caption(
#                         f"Type: {itype} | "
#                         f"Confidence: {float(ins.get('confidence', 0)):.0%}"
#                     )
#         else:
#             st.info("No insights yet. Run the agent to generate insights.")
#     except Exception as e:
#         st.error(f"Could not load insights: {e}")


# # ════════════════════════════════════════════════════════════════════════════
# # Page 6 — Stats
# # ════════════════════════════════════════════════════════════════════════════
# elif page == "📊 Stats":
#     st.title("📊 Engram Stats")
#     st.caption("Live stats from your Endee vector database")

#     try:
#         from core.indexes import ALL_INDEXES, MEMORIES_INDEX, ENTITIES_INDEX, INSIGHTS_INDEX, TIMELINE_INDEX

#         # Read directly from Endee raw SDK — bypasses all caching/wrappers
#         counts = _get_real_counts()

#         col1, col2, col3, col4 = st.columns(4)
#         col1.metric("Memory chunks",    counts.get(MEMORIES_INDEX, 0))
#         col2.metric("Entities",         counts.get(ENTITIES_INDEX, 0))
#         col3.metric("Insights",         counts.get(INSIGHTS_INDEX, 0))
#         col4.metric("Timeline entries", counts.get(TIMELINE_INDEX, 0))

#         st.divider()
#         st.markdown("### All source files")
#         try:
#             search  = get_search()
#             sources = search.get_all_sources()
#             if sources:
#                 for s in sources:
#                     st.markdown(f"- 📄 {s}")
#             else:
#                 st.info("No files uploaded yet.")
#         except Exception as e:
#             st.error(f"Could not load sources: {e}")

#         st.divider()
#         st.markdown("### Endee index details")
#         for name in ALL_INDEXES:
#             count = counts.get(name, 0)
#             st.markdown(f"**{name}**: {count} vectors")

#     except Exception as e:
#         st.error(f"Could not load stats: {e}")
#         st.exception(e)




























#         from __future__ import annotations
# import sys, os
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# import streamlit as st
# from dotenv import load_dotenv
# load_dotenv()

# st.set_page_config(
#     page_title="Engram",
#     page_icon="🧠",
#     layout="wide",
#     initial_sidebar_state="expanded",
# )

# st.markdown("""
# <style>
#   .block-container { padding-top: 1.5rem; }
#   .metric-label { font-size: 12px; }
#   .stAlert { border-radius: 8px; }
#   div[data-testid="stSidebarContent"] { padding-top: 1rem; }
# </style>
# """, unsafe_allow_html=True)


# # ── Lazy init — cached so modules load once ──────────────────────────────────

# @st.cache_resource
# def get_engine():
#     from ingestion.engine import IngestionEngine
#     return IngestionEngine()

# @st.cache_resource
# def get_search():
#     from search.search_engine import SearchEngine
#     return SearchEngine()

# @st.cache_resource
# def get_rag():
#     from rag.rag_pipeline import RAGPipeline
#     return RAGPipeline()

# @st.cache_resource
# def get_recommender():
#     from recommendations.recommender import Recommender
#     return Recommender()

# @st.cache_resource
# def get_agent():
#     from agents.monitor_agent import MonitorAgent
#     return MonitorAgent()

# @st.cache_resource
# def get_endee():
#     from utils.endee_client import EndeeClient
#     return EndeeClient()

# @st.cache_resource
# def init_indexes():
#     from core.indexes import initialise_indexes
#     return initialise_indexes()


# # ── Initialise indexes on startup ────────────────────────────────────────────
# try:
#     init_indexes()
#     endee_ok = True
# except Exception as e:
#     endee_ok = False
#     st.error(f"Cannot connect to Endee: {e}. Make sure Docker is running.")


# # ── Sidebar ──────────────────────────────────────────────────────────────────
# with st.sidebar:
#     st.markdown("## 🧠 Engram")
#     st.caption("Your personal AI second brain")
#     st.divider()

#     page = st.radio(
#         "Navigate",
#         ["🔍 Search", "💬 Ask AI", "📤 Upload", "🌐 Related", "🤖 Agent", "📊 Stats"],
#         label_visibility="collapsed",
#     )

#     st.divider()

#     # Endee status
#     if endee_ok:
#         st.success("Endee connected ✓")
#     else:
#         st.error("Endee offline ✗")

#     # Index stats
#     try:
#         from core.indexes import get_index_stats, ALL_INDEXES
#         stats = get_index_stats()
#         total = 0
#         for name in ALL_INDEXES:
#             count = stats.get(name, {}).get("vector_count", 0)
#             total += count if isinstance(count, int) else 0
#         st.metric("Total memories", total)
#     except Exception:
#         st.metric("Total memories", "—")


# # ════════════════════════════════════════════════════════════════════════════
# # Page 1 — Search
# # ════════════════════════════════════════════════════════════════════════════
# if page == "🔍 Search":
#     st.title("🔍 Search your memory")
#     st.caption("Semantic search — finds meaning, not just keywords")

#     query = st.text_input(
#         "What are you looking for?",
#         placeholder="e.g. CAP theorem, meeting with Rahul, machine learning notes...",
#     )

#     col1, col2, col3 = st.columns(3)
#     with col1:
#         file_type = st.selectbox(
#             "File type", ["All", "pdf", "text", "markdown", "csv", "docx"]
#         )
#     with col2:
#         top_k = st.slider("Results", 3, 20, 8)
#     with col3:
#         since_days = st.selectbox("Time range", ["All time", "7 days", "30 days", "90 days"])

#     days_map  = {"All time": None, "7 days": 7, "30 days": 30, "90 days": 90}
#     days_val  = days_map[since_days]
#     ft_val    = None if file_type == "All" else file_type

#     if query:
#         with st.spinner("Searching Endee..."):
#             try:
#                 search  = get_search()
#                 results = search.search(
#                     query,
#                     top_k=top_k,
#                     file_type=ft_val,
#                     since_days=days_val,
#                 )
#             except Exception as e:
#                 st.error(f"Search failed: {e}")
#                 results = []

#         if results:
#             st.success(f"Found {len(results)} memories")
#             for r in results:
#                 with st.expander(
#                     f"**{r.chunk.source_file}** — score: {r.score:.3f}",
#                     expanded=r.rank == 1,
#                 ):
#                     st.markdown(r.snippet)
#                     col_a, col_b, col_c = st.columns(3)
#                     col_a.caption(f"Type: {r.chunk.file_type.value}")
#                     col_b.caption(f"Chunk: {r.chunk.chunk_index + 1}/{r.chunk.total_chunks}")
#                     col_c.caption(f"Words: {r.chunk.word_count}")
#         else:
#             st.info("No results found. Try a different query or upload some files first.")


# # ════════════════════════════════════════════════════════════════════════════
# # Page 2 — Ask AI (RAG)
# # ════════════════════════════════════════════════════════════════════════════
# elif page == "💬 Ask AI":
#     st.title("💬 Ask your documents")
#     st.caption("RAG — answers grounded in YOUR uploaded files")

#     question = st.text_input(
#         "Ask anything about your documents",
#         placeholder="e.g. What did I decide about my career in January? What is CAP theorem?",
#     )

#     top_k_rag = st.slider("Chunks to retrieve from Endee", 3, 10, 5)

#     if question:
#         with st.spinner("Retrieving from Endee + generating answer..."):
#             try:
#                 rag      = get_rag()
#                 response = rag.query(question, top_k=top_k_rag)
#             except Exception as e:
#                 st.error(f"RAG failed: {e}")
#                 response = None

#         if response:
#             # Answer box
#             st.markdown("### Answer")
#             st.info(response.answer)

#             # Timing stats
#             col1, col2, col3 = st.columns(3)
#             col1.metric("Retrieval", f"{response.retrieval_time_ms}ms")
#             col2.metric("Generation", f"{response.generation_time_ms}ms")
#             col3.metric("Chunks used", response.chunk_count)

#             # Sources
#             if response.sources:
#                 st.markdown("### Sources from Endee")
#                 for i, src in enumerate(response.sources, 1):
#                     with st.expander(f"[{i}] {src.get('source_file', 'unknown')} — score: {src.get('score', 0):.3f}"):
#                         st.caption(src.get("content", "")[:300])


# # ════════════════════════════════════════════════════════════════════════════
# # Page 3 — Upload
# # ════════════════════════════════════════════════════════════════════════════
# elif page == "📤 Upload":
#     st.title("📤 Upload documents")
#     st.caption("Supports PDF, TXT, MD, CSV, DOCX")

#     uploaded = st.file_uploader(
#         "Drop files here",
#         type=["pdf", "txt", "md", "csv", "docx"],
#         accept_multiple_files=True,
#     )

#     extract_entities = st.checkbox("Extract entities (needs Groq key)", value=True)

#     if uploaded and st.button("Ingest into Endee", type="primary"):
#         engine = get_engine()
#         for f in uploaded:
#             with st.spinner(f"Processing {f.name}..."):
#                 try:
#                     result = engine.ingest_bytes(
#                         f.read(), f.name,
#                         extract_entities=extract_entities,
#                     )
#                     if result.success:
#                         st.success(
#                             f"✅ **{f.name}** — "
#                             f"{result.chunks_stored} chunks stored, "
#                             f"{result.duplicates_skipped} duplicates skipped, "
#                             f"{result.entities_extracted} entities, "
#                             f"{result.processing_time_ms}ms"
#                         )
#                     else:
#                         st.error(f"❌ {f.name}: {result.errors}")
#                 except Exception as e:
#                     st.error(f"❌ {f.name}: {e}")


# # ════════════════════════════════════════════════════════════════════════════
# # Page 4 — Related Memories
# # ════════════════════════════════════════════════════════════════════════════
# elif page == "🌐 Related":
#     st.title("🌐 Related memories")
#     st.caption("Find how a topic connects across all your documents")

#     topic = st.text_input(
#         "Enter a topic",
#         placeholder="e.g. system design, machine learning, career...",
#     )

#     if topic:
#         with st.spinner("Finding connections in Endee..."):
#             try:
#                 rec         = get_recommender()
#                 connections = rec.find_cross_file_connections(topic, top_k=6)
#                 forgotten   = rec.find_forgotten(query=topic, days=30, top_k=3)
#             except Exception as e:
#                 st.error(f"Failed: {e}")
#                 connections = {}
#                 forgotten   = []

#         if connections:
#             st.markdown(f"### Topic appears in {len(connections)} files")
#             for source, results in connections.items():
#                 with st.expander(f"📄 {source}"):
#                     for r in results:
#                         st.markdown(f"> {r.snippet}")
#                         st.caption(f"Similarity: {r.score:.3f}")
#         else:
#             st.info("No connections found. Upload more files to see cross-document connections.")

#         if forgotten:
#             st.divider()
#             st.markdown("### 💤 You forgot about these")
#             st.caption("Related memories you have not seen in 30+ days")
#             for r in forgotten:
#                 with st.expander(f"📄 {r.chunk.source_file}"):
#                     st.markdown(r.snippet)


# # ════════════════════════════════════════════════════════════════════════════
# # Page 5 — Agent
# # ════════════════════════════════════════════════════════════════════════════
# elif page == "🤖 Agent":
#     st.title("🤖 AI Agent")
#     st.caption("Autonomously scans your memory and generates insights")

#     st.info(
#         "The agent reads all your documents from Endee and finds: "
#         "recurring patterns, contradictions, knowledge gaps, and forgotten memories."
#     )

#     if st.button("Run Agent Now", type="primary"):
#         with st.spinner("Agent scanning your Endee memory..."):
#             try:
#                 agent  = get_agent()
#                 report = agent.run()
#             except Exception as e:
#                 st.error(f"Agent failed: {e}")
#                 report = None

#         if report:
#             st.success(f"Agent run {report.run_id} complete in {report.duration_seconds}s")
#             st.markdown(f"**Summary:** {report.summary}")

#             col1, col2, col3, col4 = st.columns(4)
#             col1.metric("Patterns", report.patterns_found)
#             col2.metric("Contradictions", report.contradictions_found)
#             col3.metric("Gaps", report.gaps_found)
#             col4.metric("Forgotten", report.forgotten_found)

#     st.divider()
#     st.markdown("### Past insights from Endee")

#     try:
#         rec      = get_recommender()
#         insights = rec.get_recent_insights(top_k=10)
#         if insights:
#             for ins in insights:
#                 itype = ins.get("insight_type", "pattern")
#                 color = {
#                     "pattern":       "🔵",
#                     "contradiction":  "🔴",
#                     "knowledge_gap":  "🟡",
#                     "forgotten_memory": "⚪",
#                 }.get(itype, "⚪")
#                 with st.expander(f"{color} {ins.get('title', 'Insight')}"):
#                     st.markdown(ins.get("description", ""))
#                     st.caption(
#                         f"Type: {itype} | "
#                         f"Confidence: {float(ins.get('confidence', 0)):.0%}"
#                     )
#         else:
#             st.info("No insights yet. Run the agent to generate insights.")
#     except Exception as e:
#         st.error(f"Could not load insights: {e}")


# # ════════════════════════════════════════════════════════════════════════════
# # Page 6 — Stats
# # ════════════════════════════════════════════════════════════════════════════
# elif page == "📊 Stats":
#     st.title("📊 Engram Stats")
#     st.caption("Live stats from your Endee vector database")

#     try:
#         from core.indexes import get_index_stats, ALL_INDEXES, MEMORIES_INDEX
#         from core.indexes import ENTITIES_INDEX, INSIGHTS_INDEX, TIMELINE_INDEX

#         stats = get_index_stats()

#         col1, col2, col3, col4 = st.columns(4)
#         col1.metric(
#             "Memory chunks",
#             stats.get(MEMORIES_INDEX, {}).get("vector_count", 0)
#         )
#         col2.metric(
#             "Entities",
#             stats.get(ENTITIES_INDEX, {}).get("vector_count", 0)
#         )
#         col3.metric(
#             "Insights",
#             stats.get(INSIGHTS_INDEX, {}).get("vector_count", 0)
#         )
#         col4.metric(
#             "Timeline entries",
#             stats.get(TIMELINE_INDEX, {}).get("vector_count", 0)
#         )

#         st.divider()
#         st.markdown("### All source files")
#         try:
#             search  = get_search()
#             sources = search.get_all_sources()
#             if sources:
#                 for s in sources:
#                     st.markdown(f"- 📄 {s}")
#             else:
#                 st.info("No files uploaded yet.")
#         except Exception as e:
#             st.error(f"Could not load sources: {e}")

#         st.divider()
#         st.markdown("### Endee index details")
#         for name in ALL_INDEXES:
#             s = stats.get(name, {})
#             st.markdown(f"**{name}**: {s}")

#     except Exception as e:
#         st.error(f"Could not load stats: {e}")


















from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(
    page_title="Engram",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  .block-container { padding-top: 1.5rem; }
  .metric-label { font-size: 12px; }
  .stAlert { border-radius: 8px; }
  div[data-testid="stSidebarContent"] { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)


# ── Lazy init — cached so modules load once ──────────────────────────────────

@st.cache_resource
def get_engine():
    from ingestion.engine import IngestionEngine
    return IngestionEngine()

@st.cache_resource
def get_search():
    from search.search_engine import SearchEngine
    return SearchEngine()

@st.cache_resource
def get_rag():
    from rag.rag_pipeline import RAGPipeline
    return RAGPipeline()

@st.cache_resource
def get_recommender():
    from recommendations.recommender import Recommender
    return Recommender()

@st.cache_resource
def get_agent():
    from agents.monitor_agent import MonitorAgent
    return MonitorAgent()

@st.cache_resource
def get_endee():
    from utils.endee_client import EndeeClient
    return EndeeClient()

@st.cache_resource
def init_indexes():
    from core.indexes import initialise_indexes
    return initialise_indexes()


# ── Helper — count vectors by querying each index ────────────────────────────
def _get_real_counts() -> dict:
    """
    Endee's total_elements is a known bug — always returns 0 after upsert.
    Fix: query each index with a neutral vector and count results returned.
    Max top_k Endee allows is 512.
    """
    try:
        from endee import Endee
        c         = Endee()
        dummy_vec = [0.01] * 384
        index_names = [
            "engram_memories",
            "engram_entities",
            "engram_insights",
            "engram_timeline",
        ]
        counts = {}
        for name in index_names:
            try:
                idx   = c.get_index(name=name)
                res   = idx.query(vector=dummy_vec, top_k=512)
                items = res.get("results", res) if isinstance(res, dict) else res
                counts[name] = len(items)
            except Exception:
                counts[name] = 0
        return counts
    except Exception:
        return {}


# ── Initialise indexes on startup ────────────────────────────────────────────
try:
    init_indexes()
    endee_ok = True
except Exception as e:
    endee_ok = False
    st.error(f"Cannot connect to Endee: {e}. Make sure Docker is running.")


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 Engram")
    st.caption("Your personal AI second brain")
    st.divider()

    page = st.radio(
        "Navigate",
        ["🔍 Search", "💬 Ask AI", "📤 Upload", "🌐 Related", "🤖 Agent", "📊 Stats"],
        label_visibility="collapsed",
    )

    st.divider()

    if endee_ok:
        st.success("Endee connected ✓")
    else:
        st.error("Endee offline ✗")

    # Sidebar count — memories only (most important number)
    try:
        counts = _get_real_counts()
        st.metric("Total memories", counts.get("engram_memories", 0))
    except Exception:
        st.metric("Total memories", "—")


# ════════════════════════════════════════════════════════════════════════════
# Page 1 — Search
# ════════════════════════════════════════════════════════════════════════════
if page == "🔍 Search":
    st.title("🔍 Search your memory")
    st.caption("Semantic search — finds meaning, not just keywords")

    query = st.text_input(
        "What are you looking for?",
        placeholder="e.g. CAP theorem, meeting with Rahul, machine learning notes...",
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        file_type = st.selectbox(
            "File type", ["All", "pdf", "text", "markdown", "csv", "docx"]
        )
    with col2:
        top_k = st.slider("Results", 3, 20, 8)
    with col3:
        since_days = st.selectbox("Time range", ["All time", "7 days", "30 days", "90 days"])

    days_map = {"All time": None, "7 days": 7, "30 days": 30, "90 days": 90}
    days_val = days_map[since_days]
    ft_val   = None if file_type == "All" else file_type

    if query:
        with st.spinner("Searching Endee..."):
            try:
                search  = get_search()
                results = search.search(
                    query,
                    top_k=top_k,
                    file_type=ft_val,
                    since_days=days_val,
                )
            except Exception as e:
                st.error(f"Search failed: {e}")
                results = []

        if results:
            st.success(f"Found {len(results)} memories")
            for r in results:
                with st.expander(
                    f"**{r.chunk.source_file}** — score: {r.score:.3f}",
                    expanded=r.rank == 1,
                ):
                    st.markdown(r.snippet)
                    col_a, col_b, col_c = st.columns(3)
                    col_a.caption(f"Type: {r.chunk.file_type.value}")
                    col_b.caption(f"Chunk: {r.chunk.chunk_index + 1}/{r.chunk.total_chunks}")
                    col_c.caption(f"Words: {r.chunk.word_count}")
        else:
            st.info("No results found. Try a different query or upload some files first.")


# ════════════════════════════════════════════════════════════════════════════
# Page 2 — Ask AI (RAG)
# ════════════════════════════════════════════════════════════════════════════
elif page == "💬 Ask AI":
    st.title("💬 Ask your documents")
    st.caption("RAG — answers grounded in YOUR uploaded files")

    question = st.text_input(
        "Ask anything about your documents",
        placeholder="e.g. What did I decide about my career in January? What is CAP theorem?",
    )

    top_k_rag = st.slider("Chunks to retrieve from Endee", 3, 10, 5)

    if question:
        with st.spinner("Retrieving from Endee + generating answer..."):
            try:
                rag      = get_rag()
                response = rag.query(question, top_k=top_k_rag)
            except Exception as e:
                st.error(f"RAG failed: {e}")
                response = None

        if response:
            st.markdown("### Answer")
            st.info(response.answer)

            col1, col2, col3 = st.columns(3)
            col1.metric("Retrieval", f"{response.retrieval_time_ms}ms")
            col2.metric("Generation", f"{response.generation_time_ms}ms")
            col3.metric("Chunks used", response.chunk_count)

            if response.sources:
                st.markdown("### Sources from Endee")
                for i, src in enumerate(response.sources, 1):
                    with st.expander(
                        f"[{i}] {src.get('source_file', 'unknown')} — score: {src.get('score', 0):.3f}"
                    ):
                        st.caption(src.get("content", "")[:300])


# ════════════════════════════════════════════════════════════════════════════
# Page 3 — Upload
# ════════════════════════════════════════════════════════════════════════════
elif page == "📤 Upload":
    st.title("📤 Upload documents")
    st.caption("Supports PDF, TXT, MD, CSV, DOCX")

    uploaded = st.file_uploader(
        "Drop files here",
        type=["pdf", "txt", "md", "csv", "docx"],
        accept_multiple_files=True,
    )

    extract_entities = st.checkbox("Extract entities (needs Groq key)", value=True)

    if uploaded and st.button("Ingest into Endee", type="primary"):
        engine = get_engine()
        for f in uploaded:
            with st.spinner(f"Processing {f.name}..."):
                try:
                    result = engine.ingest_bytes(
                        f.read(), f.name,
                        extract_entities=extract_entities,
                    )
                    if result.success:
                        st.success(
                            f"✅ **{f.name}** — "
                            f"{result.chunks_stored} chunks stored, "
                            f"{result.duplicates_skipped} duplicates skipped, "
                            f"{result.entities_extracted} entities, "
                            f"{result.processing_time_ms}ms"
                        )
                    else:
                        st.error(f"❌ {f.name}: {result.errors}")
                except Exception as e:
                    st.error(f"❌ {f.name}: {e}")


# ════════════════════════════════════════════════════════════════════════════
# Page 4 — Related Memories
# ════════════════════════════════════════════════════════════════════════════
elif page == "🌐 Related":
    st.title("🌐 Related memories")
    st.caption("Find how a topic connects across all your documents")

    topic = st.text_input(
        "Enter a topic",
        placeholder="e.g. system design, machine learning, career...",
    )

    if topic:
        with st.spinner("Finding connections in Endee..."):
            try:
                rec         = get_recommender()
                connections = rec.find_cross_file_connections(topic, top_k=6)
                forgotten   = rec.find_forgotten(query=topic, days=30, top_k=3)
            except Exception as e:
                st.error(f"Failed: {e}")
                connections = {}
                forgotten   = []

        if connections:
            st.markdown(f"### Topic appears in {len(connections)} files")
            for source, results in connections.items():
                with st.expander(f"📄 {source}"):
                    for r in results:
                        st.markdown(f"> {r.snippet}")
                        st.caption(f"Similarity: {r.score:.3f}")
        else:
            st.info("No connections found. Upload more files to see cross-document connections.")

        if forgotten:
            st.divider()
            st.markdown("### 💤 You forgot about these")
            st.caption("Related memories you have not seen in 30+ days")
            for r in forgotten:
                with st.expander(f"📄 {r.chunk.source_file}"):
                    st.markdown(r.snippet)


# ════════════════════════════════════════════════════════════════════════════
# Page 5 — Agent
# ════════════════════════════════════════════════════════════════════════════
elif page == "🤖 Agent":
    st.title("🤖 AI Agent")
    st.caption("Autonomously scans your memory and generates insights")

    st.info(
        "The agent reads all your documents from Endee and finds: "
        "recurring patterns, contradictions, knowledge gaps, and forgotten memories."
    )

    if st.button("Run Agent Now", type="primary"):
        with st.spinner("Agent scanning your Endee memory..."):
            try:
                agent  = get_agent()
                report = agent.run()
            except Exception as e:
                st.error(f"Agent failed: {e}")
                report = None

        if report:
            st.success(f"Agent run {report.run_id} complete in {report.duration_seconds}s")
            st.markdown(f"**Summary:** {report.summary}")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Patterns", report.patterns_found)
            col2.metric("Contradictions", report.contradictions_found)
            col3.metric("Gaps", report.gaps_found)
            col4.metric("Forgotten", report.forgotten_found)

    st.divider()
    st.markdown("### Past insights from Endee")

    try:
        rec      = get_recommender()
        insights = rec.get_recent_insights(top_k=10)
        if insights:
            for ins in insights:
                itype = ins.get("insight_type", "pattern")
                color = {
                    "pattern":          "🔵",
                    "contradiction":    "🔴",
                    "knowledge_gap":    "🟡",
                    "forgotten_memory": "⚪",
                }.get(itype, "⚪")
                with st.expander(f"{color} {ins.get('title', 'Insight')}"):
                    st.markdown(ins.get("description", ""))
                    st.caption(
                        f"Type: {itype} | "
                        f"Confidence: {float(ins.get('confidence', 0)):.0%}"
                    )
        else:
            st.info("No insights yet. Run the agent to generate insights.")
    except Exception as e:
        st.error(f"Could not load insights: {e}")


# ════════════════════════════════════════════════════════════════════════════
# Page 6 — Stats
# ════════════════════════════════════════════════════════════════════════════
elif page == "📊 Stats":
    st.title("📊 Engram Stats")
    st.caption("Live stats from your Endee vector database")

    try:
        from core.indexes import ALL_INDEXES, MEMORIES_INDEX, ENTITIES_INDEX, INSIGHTS_INDEX, TIMELINE_INDEX

        counts = _get_real_counts()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Memory chunks",    counts.get(MEMORIES_INDEX, 0))
        col2.metric("Entities",         counts.get(ENTITIES_INDEX, 0))
        col3.metric("Insights",         counts.get(INSIGHTS_INDEX, 0))
        col4.metric("Timeline entries", counts.get(TIMELINE_INDEX, 0))

        st.divider()
        st.markdown("### All source files")
        try:
            search  = get_search()
            sources = search.get_all_sources()
            if sources:
                for s in sources:
                    st.markdown(f"- 📄 {s}")
            else:
                st.info("No files uploaded yet.")
        except Exception as e:
            st.error(f"Could not load sources: {e}")

        st.divider()
        st.markdown("### Endee index details")
        for name in ALL_INDEXES:
            count = counts.get(name, 0)
            st.markdown(f"**{name}**: {count} vectors")

    except Exception as e:
        st.error(f"Could not load stats: {e}")
        st.exception(e)
        