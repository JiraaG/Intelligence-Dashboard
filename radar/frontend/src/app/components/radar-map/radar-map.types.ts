import type { PrimaryCategory } from '../../models/article.model';

/** Payload quando si apre una nazione da poligono o pin summary. */
export interface CountryOpenRequest {
  countryCode: string;
  /** Se settato (pallino categoria / detail), sidebar e spiderfy su quella categoria. */
  category?: PrimaryCategory;
  /** Mantieni la camera corrente (no fitBounds / dezoom). */
  preserveZoom?: boolean;
}

/** Payload click su arco bilaterale → sidebar con notizie A↔B. */
export interface RelationOpenRequest {
  sourceCountry: string;
  targetCountry: string;
  /** Zoom pin: solo questa tipologia; zoom macro: assente = tutte le categorie. */
  category?: PrimaryCategory;
}
