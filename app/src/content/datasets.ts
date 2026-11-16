/** Open datasets cleared for use. Citations are shown verbatim in every language. */
export interface DatasetCredit {
  id: string;
  citation: string;
  paperDoi: string;
  dataDoi: string;
  license: string;
}

export const DATASET_CREDITS: readonly DatasetCredit[] = [
  {
    id: 'openear',
    citation:
      'Sieber D, Erfurt P, John S, Ribeiro Dos Santos G, Schurzig D, Sørensen MS, Lenarz T. The OpenEar library of 3D models of the human temporal bone based on computed tomography and micro-slicing. Scientific Data 6, 180297 (2019).',
    paperDoi: '10.1038/sdata.2018.297',
    dataDoi: '10.5281/zenodo.1473724',
    license: 'CC BY 4.0',
  },
  {
    id: 'bern-labyrinth',
    citation:
      'Wimmer W, Anschuetz L, Weder S, Wagner F, Delingette H, Caversaccio M. Human bony labyrinth dataset: Co-registered CT and micro-CT images, surface models and anatomical landmarks. Data in Brief 27, 104782 (2019).',
    paperDoi: '10.1016/j.dib.2019.104782',
    dataDoi: '10.5281/zenodo.3355272',
    license: 'CC BY 4.0',
  },
];
