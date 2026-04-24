/**
 * Bioinformatics tools — gene prediction and structure/MD/docking (calls /api/v1/tools).
 */

import { useState } from 'react';
import { getApiErrorMessage, tools } from '../lib/api';

export default function Tools() {
  const [predictors, setPredictors] = useState<string>('');
  const [sequence, setSequence] = useState('ATGAAACCCAAATAA');
  const [contigId, setContigId] = useState('contig_1');
  const [predictor, setPredictor] = useState('orf');
  const [geneResult, setGeneResult] = useState<string>('');
  const [pdb, setPdb] = useState(`ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       1.458   0.000   0.000  1.00  0.00           C
END`);
  const [mdResult, setMdResult] = useState<string>('');
  const [proteinPdb, setProteinPdb] = useState('');
  const [ligandPdb, setLigandPdb] = useState('');
  const [pipelineResult, setPipelineResult] = useState<string>('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (label: string, fn: () => Promise<unknown>) => {
    setError(null);
    setBusy(label);
    try {
      const data = await fn();
      return data;
    } catch (e: unknown) {
      setError(getApiErrorMessage(e));
      return null;
    } finally {
      setBusy(null);
    }
  };

  const loadPredictors = async () => {
    const data = await run('predictors', () => tools.listGenePredictors());
    if (data) setPredictors(JSON.stringify(data, null, 2));
  };

  const runPredictGenes = async () => {
    const data = await run('predict', () =>
      tools.predictGenes({
        sequence: sequence.replace(/\s/g, ''),
        contig_id: contigId,
        predictor,
        include_sequences: false,
      }),
    );
    if (data) setGeneResult(JSON.stringify(data, null, 2));
  };

  const runMd = async () => {
    const data = await run('md', () =>
      tools.runMd({
        pdb,
        n_steps: 20,
        save_interval: 5,
        minimize_steps: 5,
      }),
    );
    if (data) setMdResult(JSON.stringify(data, null, 2));
  };

  const runPipeline = async () => {
    if (!proteinPdb.trim() || !ligandPdb.trim()) {
      setError('Paste protein and ligand PDB contents first.');
      return;
    }
    const data = await run('pipeline', () =>
      tools.structureMdDock({
        protein_pdb: proteinPdb,
        ligand_pdb: ligandPdb,
        md_steps: 40,
        docking_poses: 5,
      }),
    );
    if (data) setPipelineResult(JSON.stringify(data, null, 2));
  };

  return (
    <div className="space-y-8 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Bioinformatics tools</h1>
        <p className="mt-1 text-sm text-gray-600">
          Uses your session token against <code className="bg-gray-100 px-1 rounded">/api/v1/tools</code>.
          Configure <code className="bg-gray-100 px-1 rounded">TOOLS_API_KEY</code> for machine access via{' '}
          <code className="bg-gray-100 px-1 rounded">X-API-Key</code>.
        </p>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 text-red-800 text-sm px-4 py-3" role="alert">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-white shadow rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Gene prediction</h2>
          <button
            type="button"
            onClick={() => void loadPredictors()}
            disabled={busy !== null}
            className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            {busy === 'predictors' ? 'Loading…' : 'List predictors'}
          </button>
          {predictors && (
            <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto max-h-40">{predictors}</pre>
          )}
          <label htmlFor="tools-dna-sequence" className="block text-sm font-medium text-gray-700">
            DNA sequence
          </label>
          <textarea
            id="tools-dna-sequence"
            className="w-full border rounded-md p-2 text-sm font-mono h-24"
            value={sequence}
            onChange={(e) => setSequence(e.target.value)}
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div>
              <label htmlFor="tools-contig-id" className="block text-sm font-medium text-gray-700">
                Contig id
              </label>
              <input
                id="tools-contig-id"
                className="w-full border rounded-md p-2 text-sm"
                value={contigId}
                onChange={(e) => setContigId(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="tools-predictor" className="block text-sm font-medium text-gray-700">
                Predictor
              </label>
              <select
                id="tools-predictor"
                className="w-full border rounded-md p-2 text-sm"
                value={predictor}
                onChange={(e) => setPredictor(e.target.value)}
              >
              <option value="orf">orf</option>
              <option value="prodigal">prodigal</option>
              <option value="augustus">augustus</option>
              <option value="metagene">metagene</option>
              </select>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void runPredictGenes()}
            disabled={busy !== null}
            className="px-4 py-2 bg-gray-800 text-white text-sm rounded-md hover:bg-gray-900 disabled:opacity-50"
          >
            {busy === 'predict' ? 'Running…' : 'Predict genes'}
          </button>
          {geneResult && (
            <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto max-h-64">{geneResult}</pre>
          )}
        </section>

        <section className="bg-white shadow rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Molecular dynamics</h2>
          <label htmlFor="tools-md-pdb" className="block text-sm font-medium text-gray-700">
            PDB text
          </label>
          <textarea
            id="tools-md-pdb"
            className="w-full border rounded-md p-2 text-sm font-mono h-40"
            value={pdb}
            onChange={(e) => setPdb(e.target.value)}
          />
          <button
            type="button"
            onClick={() => void runMd()}
            disabled={busy !== null}
            className="px-4 py-2 bg-teal-600 text-white text-sm rounded-md hover:bg-teal-700 disabled:opacity-50"
          >
            {busy === 'md' ? 'Running…' : 'Run short MD'}
          </button>
          {mdResult && (
            <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto max-h-64">{mdResult}</pre>
          )}
        </section>
      </div>

      <section className="bg-white shadow rounded-lg p-6 space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Structure → MD → docking</h2>
        <p className="text-sm text-gray-600">
          Paste receptor and ligand as PDB strings. This can take a minute on small instances.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Protein PDB</label>
            <textarea
              className="w-full border rounded-md p-2 text-xs font-mono h-48"
              placeholder="ATOM / HETATM records…"
              value={proteinPdb}
              onChange={(e) => setProteinPdb(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Ligand PDB</label>
            <textarea
              className="w-full border rounded-md p-2 text-xs font-mono h-48"
              placeholder="Ligand coordinates…"
              value={ligandPdb}
              onChange={(e) => setLigandPdb(e.target.value)}
            />
          </div>
        </div>
        <button
          type="button"
          onClick={() => void runPipeline()}
          disabled={busy !== null}
          className="px-4 py-2 bg-indigo-700 text-white text-sm rounded-md hover:bg-indigo-800 disabled:opacity-50"
        >
          {busy === 'pipeline' ? 'Running…' : 'Run pipeline'}
        </button>
        {pipelineResult && (
          <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto max-h-96">{pipelineResult}</pre>
        )}
      </section>
    </div>
  );
}
