/**
 * Cochlear duct length estimated from the A value.
 *
 * Default method: Alexiades G, Dhanasingh A, Jolly C. Method to estimate the complete and
 * two-turn cochlear duct length. Otol Neurotol 2015;36(5):904-907.
 * Organ of Corti length, full duct: CDL(OC) = 4.16 × A − 4.
 *
 * The formula was derived from normal cochleae; it is an estimate, not a measurement,
 * and does not hold for malformed cochleae.
 */
export const CDL_DEFAULT_METHOD = 'alexiades2015_oc' as const;

export function estimateCdlOrganOfCorti(aMm: number): number {
  return 4.16 * aMm - 4;
}
