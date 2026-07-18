"""Seed demo Fase H: ~50 articoli con related_countries per archi mappa.

NON tocca Miniflux. Opzionale: svuota vault markdown (+ .lock).

Uso (dentro radar-worker o con DATABASE_URL)::

    python -m app.scripts.seed_phase_h_demo --clear-vault
    python -m app.scripts.seed_phase_h_demo --date 2026-07-18
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date
from pathlib import Path

import asyncpg

from app.core.config import DATABASE_URL, OBSIDIAN_VAULT_PATH

# Centroids approssimati (lat, lon) per pin/archi stabili.
CENTROIDS: dict[str, tuple[float, float]] = {
    "IT": (41.87, 12.57),
    "CN": (35.86, 104.20),
    "US": (37.09, -95.71),
    "RU": (61.52, 105.32),
    "UA": (48.38, 31.17),
    "IR": (32.43, 53.69),
    "DE": (51.17, 10.45),
    "FR": (46.23, 2.21),
    "AZ": (40.14, 47.58),
    "JP": (36.20, 138.25),
    "KR": (35.91, 127.77),
    "KP": (40.34, 127.51),
    "IL": (31.05, 34.85),
    "SA": (23.89, 45.08),
    "YE": (15.55, 48.52),
    "GB": (55.38, -3.44),
    "PL": (51.92, 19.15),
    "NO": (60.47, 8.47),
    "BR": (-14.24, -51.93),
    "TW": (23.70, 120.96),
    "KW": (29.31, 47.48),
    "CA": (56.13, -106.35),
    "IN": (20.59, 78.96),
    "XX": (0.0, 0.0),
}


def _clear_vault(vault_root: Path) -> int:
    """Elimina ``*.md`` e ``*.md.lock`` sotto il vault. Ritorna file rimossi."""
    removed = 0
    if not vault_root.is_dir():
        print(f"vault_missing={vault_root}")
        return 0
    for path in vault_root.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        if name.endswith(".md") or name.endswith(".md.lock"):
            try:
                path.unlink()
                removed += 1
            except OSError as exc:
                print(f"vault_err {path}: {exc}")
    return removed


# (title, summary, country, category, related, sentiment, relevance,
#  entities, companies, tags_extra, is_read, is_saved)
# tags: primary_category always first via insert helper
DEMO_ROWS: list[tuple] = [
    # --- RU ↔ UA Sicurezza (volume alto) ---
    ("Attacchi a infrastrutture energetiche in Ucraina orientale",
     "Raid notturni su sottostazioni lungo la linea del fronte; ripercussioni bilaterali.",
     "UA", "Sicurezza", ["RU"], "Negativo", 5,
     ["Sottostazione Zaporizhzhia"], ["Ukrenergo"], ["fronte"], False, False),
    ("Mosca annuncia nuove misure di difesa aerea al confine",
     "Rinforzi SAM e esercitazioni congiunte dichiarate come risposta deterrente.",
     "RU", "Sicurezza", ["UA"], "Negativo", 4,
     ["Base aerea Kursk"], ["Almaz-Antey"], ["difesa aerea"], False, False),
    ("Scambio di prigionieri mediato sul corridoio orientale",
     "Accordo tecnico bilaterale dopo settimane di negoziati indiretti.",
     "UA", "Sicurezza", ["RU"], "Neutrale", 3,
     [], ["Croce Rossa"], ["negoziati"], True, False),
    ("Sabotaggio segnalato su oleodotto di transito",
     "Interruzione breve del flusso; indagini attribuiscono responsabilità cross-border.",
     "RU", "Sicurezza", ["UA"], "Negativo", 5,
     ["Oleodotto Druzhba"], ["Transneft"], ["energia critica"], False, True),
    ("Briefing NATO su escalation lungo il Dnipro",
     "Analisi multilaterale con focus sul rischio di spillover regionale.",
     "UA", "Sicurezza", ["RU", "PL"], "Negativo", 4,
     [], ["NATO"], ["escalation"], False, False),
    # --- US ↔ IR Geopolitica ---
    ("Nuovo round di sanzioni USA sul programma missilistico iraniano",
     "Pacchetto mirato a enti di procurement e intermediari regionali.",
     "US", "Geopolitica", ["IR"], "Negativo", 5,
     [], ["Dipartimento del Tesoro"], ["sanzioni"], False, False),
    ("Teheran denuncia incursioni nel Golfo Persico",
     "Dichiarazioni ufficiali su incidenti navali e canali diplomatici tesi.",
     "IR", "Geopolitica", ["US", "KW"], "Negativo", 4,
     ["Stretto di Hormuz"], ["IRGC"], ["golfo"], False, False),
    ("Mediazione regionale su de-escalation nello stretto",
     "Iniziativa diplomatica per ridurre frizioni marittime USA–Iran.",
     "KW", "Geopolitica", ["US", "IR"], "Positivo", 3,
     [], [], ["mediazione"], True, False),
    ("Briefing sul deterrente strategico nel teatro Medioriente",
     "Valutazione congiunta di posture militari e canali di crisi.",
     "US", "Geopolitica", ["IR"], "Neutrale", 4,
     ["Base Al Udeid"], ["Pentagono"], ["deterrenza"], False, False),
    # --- IT ↔ CN Economia / Energia ---
    ("Accordo industriale Italia–Cina su componenti per rete elettrica",
     "Memorandum su forniture e standard tecnici per modernizzazione reti.",
     "IT", "Economia", ["CN"], "Positivo", 4,
     ["Rete Terna Nord"], ["Terna", "State Grid"], ["accordo"], False, False),
    ("Pechino promuove corridoio logistico verso i porti italiani",
     "Investimenti in hub intermodali e digitalizzazione doganale.",
     "CN", "Economia", ["IT"], "Positivo", 3,
     ["Porto di Genova"], ["COSCO"], ["logistica"], False, True),
    ("Tensione commerciale su dazi settoriali bilaterali",
     "Consultazioni urgenti dopo l’annuncio di misure di salvaguardia.",
     "IT", "Economia", ["CN"], "Negativo", 4,
     [], ["Confindustria"], ["dazi"], False, False),
    ("Partnership gas e stoccaggio: tavolo tecnico Roma–Pechino",
     "Studio di fattibilità su capacità di stoccaggio e swap energetici.",
     "IT", "Energia", ["CN"], "Neutrale", 3,
     ["Stoccaggio Rivolta"], ["Eni", "CNPC"], ["gas"], True, False),
    # --- AZ ↔ IT Energia (TAP) ---
    ("Aumento capacità TAP: Azerbaigian e Italia firmano addendum",
     "Incremento programmato dei flussi verso l’Europa meridionale.",
     "AZ", "Energia", ["IT"], "Positivo", 5,
     ["Gasdotto TAP"], ["SOCAR", "SNAM"], ["TAP"], False, False),
    ("Manutenzione programmata sul tratto adriatico del TAP",
     "Finestra tecnica concordata tra operatori azero e italiano.",
     "IT", "Energia", ["AZ"], "Neutrale", 3,
     ["Terminal Melendugno"], ["TAP AG"], ["manutenzione"], False, False),
    ("Forum energetico sul corridoio Sud: focus Baku–Roma",
     "Panel su sicurezza delle forniture e diversificazione.",
     "AZ", "Energia", ["IT", "DE"], "Positivo", 4,
     [], ["BP", "SOCAR"], ["corridoio sud"], True, False),
    # --- DE ↔ FR Energia / Nucleare ---
    ("Coordinamento franco-tedesco sulla rete elettrica interconnessa",
     "Accordo su scambi di picco e stabilità della rete continentale.",
     "DE", "Energia", ["FR"], "Positivo", 3,
     ["Interconnector"], ["RTE", "Amprion"], ["rete"], False, False),
    ("Parigi e Berlino aggiornano roadmap nucleare civile",
     "Allineamento su standard di sicurezza e ricerca congiunta.",
     "FR", "Nucleare", ["DE"], "Neutrale", 4,
     ["Impianto Flamanville"], ["EDF"], ["civile"], False, False),
    ("Test di stress congiunto su reattori di ricerca",
     "Esercitazione bilaterale su protocolli di emergenza radiologica.",
     "DE", "Nucleare", ["FR"], "Neutrale", 3,
     ["Centro Jülich"], ["CEA"], ["sicurezza nucleare"], True, False),
    # --- US ↔ CN Tecnologia ---
    ("Restrizioni USA su chip avanzati verso Pechino",
     "Nuove regole di export control su nodi sotto i 5 nm.",
     "US", "Tecnologia", ["CN"], "Negativo", 5,
     ["Fab TSMC Arizona"], ["NVIDIA", "TSMC"], ["semiconductor"], False, False),
    ("Cina annuncia fondi sovrani per litografia domestica",
     "Pacchetto industriale in risposta alle limitazioni occidentali.",
     "CN", "Tecnologia", ["US"], "Neutrale", 4,
     ["Parco Hi-Tech Shanghai"], ["SMIC"], ["litografia"], False, False),
    ("Summit bilaterale su standard AI e sicurezza cibernetica",
     "Dialogo tecnico su governance dei modelli e supply chain.",
     "US", "Tecnologia", ["CN"], "Positivo", 3,
     [], ["Google", "Baidu"], ["AI"], True, False),
    # --- KP ↔ KR Sicurezza ---
    ("Tensioni sulla DMZ dopo prove di artiglieria",
     "Seul e Pyongyang si scambiano accuse su violazioni del cessate il fuoco.",
     "KR", "Sicurezza", ["KP"], "Negativo", 5,
     ["DMZ Panmunjom"], [], ["penisola"], False, False),
    ("Pyongyang mostra nuovo sistema di lancio a corto raggio",
     "Parata e comunicati che citano esplicitamente il rivale meridionale.",
     "KP", "Sicurezza", ["KR"], "Negativo", 4,
     [], [], ["missile"], False, False),
    # --- IL ↔ IR Sicurezza ---
    ("Intercettazioni dichiarate su minaccia missilistica regionale",
     "Difesa aerea israeliana in allerta elevata verso il teatro iraniano.",
     "IL", "Sicurezza", ["IR"], "Negativo", 5,
     ["Batteria Iron Dome"], ["Rafael"], ["missile defense"], False, False),
    ("Teheran conferma esercitazioni navali nel Golfo",
     "Messaggio deterrente rivolto a rivali regionali e partner occidentali.",
     "IR", "Sicurezza", ["IL", "US"], "Negativo", 4,
     ["Base Bandar Abbas"], [], ["golfo"], False, False),
    # --- SA ↔ YE Sicurezza ---
    ("Riad rafforza il dispositivo al confine meridionale",
     "Trasferimenti di unità e assetti radar dopo incidenti transfrontalieri.",
     "SA", "Sicurezza", ["YE"], "Negativo", 4,
     ["Base Najran"], [], ["confine"], False, False),
    ("Tregua locale nello Yemen: monitoraggio internazionale",
     "Accordo fragile con garanti regionali e canali verso Riyadh.",
     "YE", "Sicurezza", ["SA"], "Positivo", 3,
     [], ["ONU"], ["tregua"], True, False),
    # --- GB ↔ RU Geopolitica ---
    ("Londra espelle diplomatici dopo caso di spionaggio",
     "Misure simmetriche annunciate tra Regno Unito e Federazione Russa.",
     "GB", "Geopolitica", ["RU"], "Negativo", 4,
     [], ["FCDO"], ["diplomazia"], False, False),
    ("Mosca risponde con sanzioni su enti britannici",
     "Lista nera su think-tank e società di consulenza di sicurezza.",
     "RU", "Geopolitica", ["GB"], "Negativo", 3,
     [], [], ["sanzioni"], False, False),
    # --- JP ↔ US Spazio ---
    ("Missione congiunta JAXA–NASA su habitat lunare",
     "Accordo su moduli abitativi e finestre di lancio condivise.",
     "JP", "Spazio", ["US"], "Positivo", 4,
     ["Centro Tanegashima"], ["JAXA", "NASA"], ["Artemis"], False, False),
    ("Washington conferma payload USA su razzo giapponese",
     "Integrazione satellitare civile-militare dual-use dichiarata.",
     "US", "Spazio", ["JP"], "Positivo", 3,
     ["Cape Canaveral"], ["SpaceX", "JAXA"], ["payload"], True, False),
    # --- BR ↔ CN Economia ---
    ("Brasilia e Pechino ampliano swap in moneta locale",
     "Riduzione della dipendenza dal dollaro nel commercio bilaterale.",
     "BR", "Economia", ["CN"], "Positivo", 3,
     [], ["Banco Central", "PBOC"], ["swap"], False, False),
    ("Investimenti cinesi in infrastrutture portuali brasiliane",
     "MOU su dragaggio e digitalizzazione doganale nei porti atlanti.",
     "BR", "Infrastrutture", ["CN"], "Positivo", 4,
     ["Porto di Santos"], ["China Merchants"], ["porto"], False, False),
    # --- UA ↔ PL Infrastrutture ---
    ("Corridoio ferroviario Ucraina–Polonia potenziato",
     "Nuovi binari e controlli doganali accelerati per export cerealicolo.",
     "UA", "Infrastrutture", ["PL"], "Positivo", 4,
     ["Valico Medyka"], ["PKP"], ["grano"], False, False),
    ("Varsavia finanzia hub logistici di frontiera",
     "Fondi per magazzini refrigerati e scambi energetici di emergenza.",
     "PL", "Infrastrutture", ["UA"], "Positivo", 3,
     ["Hub Rzeszów"], [], ["logistica"], True, False),
    # --- NO ↔ RU Ambiente ---
    ("Allarme ambientale su sversamento nel Mare di Barents",
     "Monitoraggio congiunto involuntario dopo incidente offshore.",
     "NO", "Ambiente", ["RU"], "Negativo", 4,
     ["Piattaforma Barents"], ["Equinor"], ["petrolio"], False, False),
    ("Dialogo artico su emissioni da shipping",
     "Tavolo tecnico su rotte artiche e limiti di zolfo.",
     "NO", "Ambiente", ["RU"], "Neutrale", 2,
     [], ["IMO"], ["artico"], False, False),
    # --- TW ↔ CN Tecnologia ---
    ("Taipei rafforza controlli su export di attrezzature chip",
     "Allineamento alle restrizioni internazionali verso la Cina continentale.",
     "TW", "Tecnologia", ["CN"], "Negativo", 4,
     ["Fab Hsinchu"], ["TSMC"], ["export control"], False, False),
    ("Pechino accelera cluster AI in risposta a Taipei",
     "Incentivi fiscali per data center e GPU domestiche.",
     "CN", "Tecnologia", ["TW"], "Neutrale", 3,
     ["Cluster Shenzhen"], ["Huawei"], ["AI"], False, False),
    # --- Salute / altri con link leggeri ---
    ("Collaborazione OMS Italia–India su vaccini pandemici",
     "Accordo su capacità produttiva e trasferimento tecnologico.",
     "IT", "Salute", ["IN"], "Positivo", 3,
     ["Stabilimento Pomezia"], ["GSK", "Serum Institute"], ["vaccini"], False, False),
    ("Allerta sanitaria congiunta su focolaio transfrontaliero",
     "Protocolli di screening tra Canada e Stati Uniti.",
     "CA", "Salute", ["US"], "Negativo", 3,
     [], ["CDC", "PHAC"], ["epidemia"], True, False),
    # --- Articoli senza related (controllo UI: no chip / no arco) ---
    ("Aggiornamento meteo estremo sulle Alpi italiane",
     "Allerta arancione per rischio idrogeologico senza dimensione internazionale.",
     "IT", "Ambiente", [], "Negativo", 2,
     ["Bacino Po"], [], ["meteo"], False, False),
    ("Inaugurazione data center neutrale in Germania",
     "Apertura di un campus hyperscale senza partner esteri dichiarati.",
     "DE", "Tecnologia", [], "Positivo", 2,
     ["Campus Francoforte"], ["SAP"], ["cloud"], False, False),
    ("Report domestico su riforma sanitaria francese",
     "Dibattito parlamentare interno senza riferimenti bilaterali.",
     "FR", "Salute", [], "Neutrale", 2,
     [], [], ["riforma"], True, False),
    ("Lancio satellitare commerciale indipendente indiano",
     "Missione LEO civile senza payload esteri dichiarati.",
     "IN", "Spazio", [], "Positivo", 3,
     ["Sriharikota"], ["ISRO"], ["LEO"], False, False),
    ("Piano nazionale infrastrutture stradali in Polonia",
     "Finanziamento interno per riqualificazione A1–A2.",
     "PL", "Infrastrutture", [], "Positivo", 2,
     ["Autostrada A2"], [], ["trasporti"], False, False),
    ("Briefing nucleare civile solo Giappone",
     "Riavvio controllato di un reattore dopo ispezioni nazionali.",
     "JP", "Nucleare", [], "Neutrale", 3,
     ["Impianto Sendai"], ["TEPCO"], ["riavvio"], False, False),
    ("Mercato azionario brasiliano: seduta volatile",
     "Analisi macro domestica senza spillover geopolitico esplicito.",
     "BR", "Economia", [], "Neutrale", 1,
     [], ["B3"], ["mercati"], True, False),
    ("Aggiornamento sicurezza cibernetica domestica UK",
     "Linee guida NCSC per operatori critici nazionali.",
     "GB", "Sicurezza", [], "Neutrale", 2,
     [], ["NCSC"], ["cyber"], False, False),
]


async def _upsert_company(conn: asyncpg.Connection, name: str) -> int:
    await conn.execute(
        "INSERT INTO companies (name) VALUES ($1) ON CONFLICT (name) DO NOTHING",
        name,
    )
    return int(await conn.fetchval("SELECT id FROM companies WHERE name = $1", name))


async def _upsert_tag(conn: asyncpg.Connection, name: str) -> int:
    await conn.execute(
        "INSERT INTO tags (name) VALUES ($1) ON CONFLICT (name) DO NOTHING",
        name,
    )
    return int(await conn.fetchval("SELECT id FROM tags WHERE name = $1", name))


async def seed(pub_date: date, *, replace_day: bool) -> None:
    if len(DEMO_ROWS) < 45:
        raise SystemExit(f"Expected ~50 demo rows, got {len(DEMO_ROWS)}")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        if replace_day:
            deleted = await conn.execute(
                "DELETE FROM articles WHERE published_at = $1 OR source_url LIKE $2",
                pub_date,
                "https://phase-h-demo.local/%",
            )
            print(f"deleted_prior={deleted}")

        inserted = 0
        async with conn.transaction():
            for i, row in enumerate(DEMO_ROWS):
                (
                    title,
                    summary,
                    country,
                    category,
                    related,
                    sentiment,
                    relevance,
                    entities,
                    companies,
                    tags_extra,
                    is_read,
                    is_saved,
                ) = row
                lat, lon = CENTROIDS.get(country, (0.0, 0.0))
                url = f"https://phase-h-demo.local/{pub_date.isoformat()}/{i:03d}"
                article_id = await conn.fetchval(
                    """
                    INSERT INTO articles (
                        title, summary, published_at, source_url,
                        country_code, latitude, longitude, primary_category,
                        sentiment, relevance_level, is_read, is_saved,
                        infrastructural_entities, feed_title, related_countries
                    ) VALUES (
                        $1, $2, $3, $4,
                        $5, $6, $7, $8,
                        $9, $10, $11, $12,
                        $13, $14, $15
                    )
                    RETURNING id
                    """,
                    title,
                    summary,
                    pub_date,
                    url,
                    country,
                    lat,
                    lon,
                    category,
                    sentiment,
                    relevance,
                    is_read,
                    is_saved,
                    entities,
                    "phase-h-demo",
                    related,
                )
                tag_names = [category, *tags_extra]
                for tname in tag_names:
                    tid = await _upsert_tag(conn, tname)
                    await conn.execute(
                        """
                        INSERT INTO article_tags (article_id, tag_id)
                        VALUES ($1, $2) ON CONFLICT DO NOTHING
                        """,
                        article_id,
                        tid,
                    )
                for cname in companies:
                    cid = await _upsert_company(conn, cname)
                    await conn.execute(
                        """
                        INSERT INTO article_companies (article_id, company_id)
                        VALUES ($1, $2) ON CONFLICT DO NOTHING
                        """,
                        article_id,
                        cid,
                    )
                inserted += 1

        with_rel = await conn.fetchval(
            """
            SELECT COUNT(*) FROM articles
            WHERE published_at = $1 AND cardinality(related_countries) > 0
            """,
            pub_date,
        )
        edges = await conn.fetch(
            """
            SELECT
              LEAST(a.country_code, r.related) AS source_country,
              GREATEST(a.country_code, r.related) AS target_country,
              a.primary_category,
              COUNT(*)::int AS volume
            FROM articles a
            CROSS JOIN LATERAL unnest(a.related_countries) AS r(related)
            WHERE a.published_at = $1
              AND a.country_code <> 'XX'
              AND r.related <> 'XX'
              AND r.related <> a.country_code
            GROUP BY 1, 2, 3
            ORDER BY volume DESC, source_country, target_country
            """,
            pub_date,
        )
        print(f"inserted={inserted} with_related={with_rel} edge_rows={len(edges)}")
        for e in edges[:12]:
            print(
                f"  edge {e['source_country']}-{e['target_country']} "
                f"{e['primary_category']} n={e['volume']}"
            )
        if len(edges) > 12:
            print(f"  ... and {len(edges) - 12} more edges")
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Fase H demo articles (no Miniflux).")
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="published_at YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--clear-vault",
        action="store_true",
        help="Delete all *.md and *.md.lock under OBSIDIAN_VAULT_PATH",
    )
    parser.add_argument(
        "--keep-day",
        action="store_true",
        help="Do not delete prior articles for the date / demo URLs before insert",
    )
    args = parser.parse_args()
    pub_date = date.fromisoformat(args.date)

    if args.clear_vault:
        removed = _clear_vault(Path(OBSIDIAN_VAULT_PATH))
        print(f"vault_removed_files={removed} root={OBSIDIAN_VAULT_PATH}")

    asyncio.run(seed(pub_date, replace_day=not args.keep_day))


if __name__ == "__main__":
    main()
