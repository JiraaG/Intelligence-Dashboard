import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { Article, CountrySummary, PrimaryCategory } from '../models/article.model';

const TODAY = new Date().toISOString().split('T')[0];

export const MOCK_ARTICLES: Article[] = [
  // --- CLUSTER TEST: Due articoli in Germania (città diverse) ---
  {
    id: 1,
    title: 'TSMC inaugura la prima fab europea a Dresda',
    summary: 'TSMC ha inaugurato in Sassonia il primo impianto produttivo europeo per chip a 28nm. La Germania consolida il suo ruolo di hub semiconduttore del continente.',
    published_at: TODAY,
    source_url: 'https://example.com/tsmc-dresden',
    country_code: 'DE',
    latitude: 51.0504,
    longitude: 13.7373,
    companies_involved: ['TSMC', 'Infineon', 'Bosch'],
    tags: ['Chip', 'Semiconduttori', 'Germania', 'Fab'],
    primary_category: 'Chip',
    sentiment: 'Positivo',
    relevance_level: 4,
    infrastructural_entities: ['TSMC Dresden Fab', 'Silicon Saxony Campus'],
    feed_title: 'Silicon Saxony News'
  },
  {
    id: 2,
    title: 'Siemens Energy amplia la rete di trasmissione ad alta tensione in Baviera',
    summary: 'Siemens Energy ha completato il potenziamento di 800km di linee di trasmissione nel sud della Germania.',
    published_at: TODAY,
    source_url: 'https://example.com/siemens-baviera',
    country_code: 'DE',
    latitude: 48.1351,
    longitude: 11.5820,
    companies_involved: ['Siemens Energy', 'Tennet'],
    tags: ['Energia', 'Grid', 'Germania', 'Rinnovabili'],
    primary_category: 'Energia',
    sentiment: 'Neutrale',
    relevance_level: 3,
    infrastructural_entities: ['Rete di trasmissione 380kV Baviera', 'Interconnessione DE-AT'],
    feed_title: 'Bavarian Grid Monitor'
  },
  // --- CLUSTER TEST: Due articoli vicini in Ucraina ---
  {
    id: 3,
    title: 'Centrale di Zaporizhzhia: rapporto IAEA sui sistemi di raffreddamento',
    summary: "L'IAEA certifica il funzionamento dei sistemi di backup della centrale. La missione permanente rimane sul posto.",
    published_at: TODAY,
    source_url: 'https://example.com/zaporizhzhia-iaea',
    country_code: 'UA',
    latitude: 47.5083,
    longitude: 34.3981,
    companies_involved: ['IAEA', 'Energoatom', 'Rosatom'],
    tags: ['Nucleare', 'IAEA', 'Ucraina', 'Sicurezza'],
    primary_category: 'Nucleare',
    sentiment: 'Negativo',
    relevance_level: 5,
    infrastructural_entities: ['Centrale Nucleare di Zaporizhzhia', 'Sito di stoccaggio combustibile'],
    feed_title: 'IAEA Bulletin'
  },
  {
    id: 4,
    title: 'Diga di Kakhovka: progetto di ricostruzione approvato dall\'UE',
    summary: "L'Unione Europea ha approvato 2.3 miliardi di euro per la ricostruzione dell'infrastruttura idrica nel sud dell'Ucraina.",
    published_at: TODAY,
    source_url: 'https://example.com/kakhovka-ue',
    country_code: 'UA',
    latitude: 47.3606,
    longitude: 33.4750,
    companies_involved: ['European Commission', 'EBRD'],
    tags: ['Acqua', 'Diga', 'Ucraina', 'Ricostruzione'],
    primary_category: 'Acqua',
    sentiment: 'Positivo',
    relevance_level: 3,
    infrastructural_entities: ['Diga di Kakhovka', 'Serbatoio di Kakhovka'],
    feed_title: 'EU Reconstruction Index'
  },
  // --- SINGOLI MARKER: Test hatching multi-categoria ---
  {
    id: 5,
    title: 'Iran accelera arricchimento uranio, IAEA convoca riunione di emergenza',
    summary: 'Le centrifughe iraniane hanno raggiunto una capacità di arricchimento record al 60%.',
    published_at: TODAY,
    source_url: 'https://example.com/iran-uranium',
    country_code: 'IR',
    latitude: 32.4279,
    longitude: 53.6880,
    companies_involved: ['IAEA'],
    tags: ['Nucleare', 'Iran', 'IAEA', 'ONU', 'Geopolitica'],
    primary_category: 'Nucleare',
    sentiment: 'Negativo',
    relevance_level: 5,
    infrastructural_entities: ['Impianto di Natanz', 'Impianto di Fordow'],
    feed_title: 'United Nations Security News'
  },
  {
    id: 6,
    title: 'Samsung avvia produzione chip 2nm a Seoul: sfida diretta a TSMC',
    summary: 'Samsung Electronics ha avviato la produzione di massa di chip a 2nm nel suo impianto di Hwaseong.',
    published_at: TODAY,
    source_url: 'https://example.com/samsung-2nm',
    country_code: 'KR',
    latitude: 37.5665,
    longitude: 126.9780,
    companies_involved: ['Samsung Electronics', 'TSMC', 'Apple'],
    tags: ['Chip', 'Samsung', 'Corea del Sud', '2nm', 'Semiconduttori'],
    primary_category: 'Chip',
    sentiment: 'Positivo',
    relevance_level: 4,
    infrastructural_entities: ['Samsung Fab Hwaseong', 'Samsung R&D Campus Suwon'],
    feed_title: 'Korea Tech Herald'
  },
  {
    id: 7,
    title: 'Pipeline TAP: record storico di esportazione gas dall\'Azerbaigian all\'Europa',
    summary: 'Il gasdotto Trans-Adriatico ha trasportato 12 miliardi di m³ nel primo semestre 2026.',
    published_at: TODAY,
    source_url: 'https://example.com/tap-record',
    country_code: 'AZ',
    latitude: 40.1431,
    longitude: 47.5769,
    companies_involved: ['TAP AG', 'SOCAR', 'BP', 'SNAM'],
    tags: ['Energia', 'Gas', 'Pipeline', 'Azerbaijan', 'Europa'],
    primary_category: 'Energia',
    sentiment: 'Positivo',
    relevance_level: 4,
    infrastructural_entities: ['Trans-Adriatic Pipeline (TAP)', 'Terminale di Melendugno', 'Campo di Shah Deniz II'],
    feed_title: 'Trans-Adriatic Pipeline Press'
  }
];

@Injectable({ providedIn: 'root' })
export class ArticleMockService {
  getArticles(date: string): Observable<Article[]> {
    return of(MOCK_ARTICLES);
  }

  getCountries(date: string): Observable<CountrySummary[]> {
    const grouped = new Map<string, { cats: Set<string>; count: number }>();
    for (const a of MOCK_ARTICLES) {
      const entry = grouped.get(a.country_code) ?? { cats: new Set<string>(), count: 0 };
      entry.cats.add(a.primary_category);
      entry.count++;
      grouped.set(a.country_code, entry);
    }
    const result: CountrySummary[] = [];
    grouped.forEach((v, k) => {
      result.push({
        country_code: k,
        categories: [...v.cats] as PrimaryCategory[],
        article_count: v.count
      });
    });
    return of(result);
  }
}
