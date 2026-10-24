export type BirthDetails = {
  date: string;
  time: string;
  latitude: number;
  longitude: number;
  utc_offset_hours: number;
  place_name?: string | null;
  date_known?: boolean;
};

export type User = {
  email: string;
  name: string;
  email_verified: boolean;
  is_admin?: boolean;
  birth_details: BirthDetails;
};

export type ChartSummary = {
  rasi: string | null;
  nakshatra: string | null;
  lagna: string | null;
  lagna_degree?: number | null;
  sun_sign?: string | null;
};

export type Nakshatra = {
  number: number;
  name: string;
  south_name: string;
  symbol: string;
  deity: string;
  ruling_planet: string;
  gana: string;
  yoni: string;
  nadi: string;
  theme: string;
  span: { start: string; end: string };
};

export type RunResponse = {
  answer: string;
  conversation_id: string;
  session_id: string;
  execution_trace: { step: string; specialist?: string; specialists?: string[]; conclusion?: string }[];
};
