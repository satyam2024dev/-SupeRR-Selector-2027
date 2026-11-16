export type RoleType = 'batters' | 'bowlers';
export type RatingMode = 'shrunk' | 'raw';

export interface HeroStats {
  matches: number;
  deliveries: number;
  highPressureBalls: number;
  iplMatches: number;
  t20iMatches: number;
  eligibleBatters: number;
  eligibleBowlers: number;
}

export interface LeveragePoint {
  over: number;
  innings1: number;
  innings2: number;
  phase: string;
}

export interface BehaviorComparison {
  metric: string;
  normal: number;
  highPressure: number;
  delta: string;
  unit: string;
  category: 'batting' | 'bowling';
  narrative: string;
}

export interface Player {
  rank: number;
  name: string;
  team: string;
  balls: number;
  innings: number;
  rawRating: number;
  shrunkRating: number;
  uplift: number;
  consistency: number;
  score: number;
  pTop10: number;
  confidence: 'Secure' | 'Likely' | 'Close call';
  role: string;
  badge?: string;
  bootMedian: number;
  bootLow: number;
  bootHigh: number;
  iplRaw: number | null;
  t20iRaw: number | null;
  // Batter specific
  srHP?: number;
  srN?: number;
  dismHP?: number;
  dismN?: number;
  // Bowler specific
  econHP?: number;
  econN?: number;
  wktsHP?: number;
  wktsN?: number;
}

export interface NextInLine {
  name: string;
  score: number;
  role: string;
}

export interface SensitivityRow {
  condition: string;
  batters: number;
  bowlers: number;
  category: string;
}

export interface MethodologyItem {
  id: string;
  title: string;
  summary: string;
  details: string;
}

export interface PressureDataset {
  heroStats: HeroStats;
  leverageByOver: LeveragePoint[];
  behaviorComparison: BehaviorComparison[];
  calloutStat: string;
  top10Batters: Player[];
  nextInLineBatters: NextInLine[];
  top10Bowlers: Player[];
  nextInLineBowlers: NextInLine[];
  sensitivityMatrix: SensitivityRow[];
  methodology: MethodologyItem[];
  limitations: string[];
}
