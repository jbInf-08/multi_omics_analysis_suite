/**
 * Multi-Omics Integration Page
 *
 * Every figure on this page comes from POST /omics/integrate. Nothing is
 * simulated: selecting fewer than two stored datasets, or datasets that share
 * no samples, produces an error rather than a result.
 */

import { useMemo, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import {
  biomarkers as biomarkersApi,
  datasets as datasetsApi,
  getApiErrorMessage,
  omics as omicsApi,
  projects as projectsApi,
  type BiomarkerResult,
  type IntegrationResult,
} from '../lib/api';
import { useAuthStore } from '../stores/auth';

/**
 * Only methods the API implements. Each is listed with what it actually
 * reports: the decomposition methods attribute variance across the omics
 * blocks, the network methods do not, and pathway needs definitions supplied.
 */
const integrationMethods = [
  {
    id: 'intermediate_fusion',
    name: 'Intermediate Fusion',
    description: 'Joint dimensionality reduction across the selected datasets',
    reports: 'Reports variance explained and per-dataset contributions.',
  },
  {
    id: 'early_fusion',
    name: 'Early Fusion',
    description: 'Concatenate scaled features, then reduce jointly',
    reports: 'Reports variance explained and per-dataset contributions.',
  },
  {
    id: 'snf',
    name: 'Similarity Network Fusion',
    description: 'Fuse patient similarity networks from each omics',
    reports: 'Clusters and sample layout only — no per-dataset attribution.',
  },
  {
    id: 'network_integration',
    name: 'Network Integration',
    description: 'Average the per-omics sample similarity networks',
    reports: 'Clusters and sample layout only — no per-dataset attribution.',
  },
  {
    id: 'pathway_integration',
    name: 'Pathway-level Integration',
    description: 'Score samples against pathway definitions, then integrate',
    reports: 'Requires a GMT file of pathway definitions.',
  },
];

/** Methods that need pathway definitions before they can run. */
const PATHWAY_METHODS = new Set(['pathway_integration']);

/** Methods that fuse similarity networks rather than decomposing features. */
const NETWORK_METHODS = new Set(['snf', 'network_integration']);

const OMICS_FILL: Record<string, string> = {
  transcriptomics: 'fill-blue-500',
  proteomics: 'fill-green-500',
  metabolomics: 'fill-purple-500',
  genomics: 'fill-red-500',
  epigenomics: 'fill-yellow-500',
  lipidomics: 'fill-pink-500',
};

const CLUSTER_FILL = [
  'fill-blue-500',
  'fill-green-500',
  'fill-purple-500',
  'fill-red-500',
  'fill-yellow-500',
  'fill-pink-500',
  'fill-indigo-500',
  'fill-teal-500',
];

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

/** Scatter of the fused space, coloured by cluster assignment. */
function EmbeddingPlot({ result }: { result: IntegrationResult }) {
  const points = result.embedding;
  const isNetwork = NETWORK_METHODS.has(result.method);

  const scaled = useMemo(() => {
    if (points.length === 0) return [];
    const xs = points.map((p) => p.x);
    const ys = points.map((p) => p.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    // Guard against a degenerate axis (all points identical on one axis).
    const spanX = maxX - minX || 1;
    const spanY = maxY - minY || 1;
    return points.map((p) => ({
      ...p,
      cx: 5 + ((p.x - minX) / spanX) * 90,
      cy: 95 - ((p.y - minY) / spanY) * 90,
    }));
  }, [points]);

  if (scaled.length === 0) {
    return (
      <p className="text-sm text-gray-500">No samples were returned for this integration.</p>
    );
  }

  return (
    <figure className="m-0">
      <svg
        viewBox="0 0 100 100"
        className="block h-64 w-full rounded bg-gray-50"
        role="img"
        aria-label={`Fused sample space: ${scaled.length} samples in ${result.n_clusters} cluster${
          result.n_clusters === 1 ? '' : 's'
        }`}
      >
        {scaled.map((p) => (
          <circle
            key={p.sample}
            cx={p.cx}
            cy={p.cy}
            r={1.4}
            className={CLUSTER_FILL[p.cluster % CLUSTER_FILL.length]}
            opacity={0.85}
          >
            <title>{`${p.sample} — cluster ${p.cluster + 1}`}</title>
          </circle>
        ))}
      </svg>
      <figcaption className="mt-2 text-xs text-gray-500">
        {isNetwork
          ? 'Spectral embedding of the fused similarity network. Colour indicates the cluster assigned by spectral clustering, with k chosen by silhouette score.'
          : 'First two components of the fused space. Colour indicates the cluster assigned by k-means, with k chosen by silhouette score.'}
      </figcaption>
    </figure>
  );
}

export default function Integration() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [selectedDatasetIds, setSelectedDatasetIds] = useState<string[]>([]);
  const [selectedMethod, setSelectedMethod] = useState('intermediate_fusion');
  const [nComponents, setNComponents] = useState(10);
  const [pathwayFile, setPathwayFile] = useState('');
  const [analysisType, setAnalysisType] = useState('differential');
  const [featureSelection, setFeatureSelection] = useState('stability');
  const [cvFolds, setCvFolds] = useState(5);
  const [outcomeColumn, setOutcomeColumn] = useState('');
  const [eventColumn, setEventColumn] = useState('');
  const [discovery, setDiscovery] = useState<BiomarkerResult | null>(null);
  const [result, setResult] = useState<IntegrationResult | null>(null);

  const { data: projectsData } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.list({ page: 1, page_size: 100 }),
    enabled: isAuthenticated,
  });

  const { data: datasetsData, isLoading: datasetsLoading } = useQuery({
    queryKey: ['datasets', selectedProjectId],
    queryFn: () =>
      datasetsApi.list({ project_id: selectedProjectId, page: 1, page_size: 100 }),
    enabled: isAuthenticated && Boolean(selectedProjectId),
  });

  const availableDatasets = datasetsData?.items ?? [];

  const integrateMutation = useMutation({
    mutationFn: () =>
      omicsApi.integrate({
        project_id: selectedProjectId,
        dataset_ids: selectedDatasetIds,
        method: selectedMethod,
        n_components: nComponents,
        pathway_file: pathwayFile.trim() || undefined,
      }),
    onSuccess: (data) => {
      setResult(data);
      toast.success(`Integrated ${data.n_samples} samples across ${data.n_omics} datasets`);
    },
    onError: (err: unknown) => {
      setResult(null);
      toast.error(getApiErrorMessage(err));
    },
  });

  const discoverMutation = useMutation({
    mutationFn: () =>
      biomarkersApi.discover({
        project_id: selectedProjectId,
        dataset_ids: selectedDatasetIds,
        analysis_type: analysisType,
        outcome_column: outcomeColumn.trim(),
        event_column: eventColumn.trim() || null,
        feature_selection: featureSelection,
        cv_folds: cvFolds,
      }),
    onSuccess: (data) => {
      setDiscovery(data);
      toast.success(`${data.biomarkers.length} biomarkers from ${data.n_features_tested} features`);
    },
    onError: (err: unknown) => {
      setDiscovery(null);
      toast.error(getApiErrorMessage(err));
    },
  });

  const toggleDataset = (datasetId: string) => {
    setSelectedDatasetIds((prev) =>
      prev.includes(datasetId) ? prev.filter((id) => id !== datasetId) : [...prev, datasetId]
    );
    setResult(null);
    setDiscovery(null);
  };

  const canRun = selectedDatasetIds.length >= 2 && Boolean(selectedMethod);
  const canDiscover = selectedDatasetIds.length >= 1 && outcomeColumn.trim().length > 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Multi-Omics Integration</h1>
        <p className="mt-1 text-sm text-gray-500">
          Integrate multiple omics datasets for comprehensive analysis
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Dataset selection */}
        <div className="lg:col-span-2 bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Datasets</h2>

          <div className="mb-4">
            <label htmlFor="project" className="block text-sm font-medium text-gray-700 mb-1">
              Project
            </label>
            <select
              id="project"
              className="block w-full rounded-md border-gray-300 shadow-sm text-sm"
              value={selectedProjectId}
              onChange={(e) => {
                setSelectedProjectId(e.target.value);
                setSelectedDatasetIds([]);
                setResult(null);
              }}
            >
              <option value="">Select a project…</option>
              {(projectsData?.items ?? []).map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>

          {!selectedProjectId && (
            <p className="text-sm text-gray-500">Choose a project to list its datasets.</p>
          )}

          {selectedProjectId && datasetsLoading && (
            <p className="text-sm text-gray-500">Loading datasets…</p>
          )}

          {selectedProjectId && !datasetsLoading && availableDatasets.length === 0 && (
            <p className="text-sm text-gray-500">
              This project has no datasets yet. Upload at least two to integrate.
            </p>
          )}

          {availableDatasets.length > 0 && (
            <fieldset>
              <legend className="text-sm font-medium text-gray-700 mb-2">
                Select at least two datasets
              </legend>
              <div className="space-y-2">
                {availableDatasets.map((dataset) => (
                  <label
                    key={dataset.id}
                    className="flex items-center gap-3 rounded-md border border-gray-200 p-3 hover:bg-gray-50"
                  >
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-gray-300"
                      checked={selectedDatasetIds.includes(dataset.id)}
                      onChange={() => toggleDataset(dataset.id)}
                    />
                    <span className="flex-1 text-sm text-gray-900">{dataset.name}</span>
                    <span className="text-xs text-gray-500">{dataset.omics_type}</span>
                    <span className="text-xs text-gray-400">
                      {dataset.sample_count ?? '—'} samples · {dataset.feature_count ?? '—'} features
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
          )}
        </div>

        {/* Method */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Method</h2>

          <fieldset className="space-y-2">
            <legend className="sr-only">Integration method</legend>
            {integrationMethods.map((method) => (
              <label
                key={method.id}
                className="flex items-start gap-3 rounded-md border border-gray-200 p-3 hover:bg-gray-50"
              >
                <input
                  type="radio"
                  name="method"
                  className="mt-1 h-4 w-4 border-gray-300"
                  value={method.id}
                  checked={selectedMethod === method.id}
                  onChange={() => {
                    setSelectedMethod(method.id);
                    setResult(null);
                  }}
                />
                <span>
                  <span className="block text-sm font-medium text-gray-900">{method.name}</span>
                  <span className="block text-xs text-gray-500">{method.description}</span>
                  <span className="mt-1 block text-xs text-gray-400">{method.reports}</span>
                </span>
              </label>
            ))}
          </fieldset>

          {PATHWAY_METHODS.has(selectedMethod) && (
            <div className="mt-4">
              <label htmlFor="pathways" className="block text-sm font-medium text-gray-700 mb-1">
                Pathway definitions (GMT)
              </label>
              <input
                id="pathways"
                type="text"
                value={pathwayFile}
                placeholder="/path/to/pathways.gmt"
                onChange={(e) => {
                  setPathwayFile(e.target.value);
                  setResult(null);
                }}
                className="block w-full rounded-md border-gray-300 shadow-sm text-sm"
              />
              <p className="mt-1 text-xs text-gray-500">
                Required. The built-in gene sets are illustrative examples, not a basis for
                interpreting real data, so this method will not run without a file.
              </p>
            </div>
          )}

          <div className="mt-4">
            <label htmlFor="components" className="block text-sm font-medium text-gray-700 mb-1">
              Components retained
            </label>
            <input
              id="components"
              type="number"
              min={2}
              max={100}
              value={nComponents}
              onChange={(e) => {
                setNComponents(Number(e.target.value));
                setResult(null);
              }}
              className="block w-full rounded-md border-gray-300 shadow-sm text-sm"
            />
            <p className="mt-1 text-xs text-gray-500">
              Contributions are shares of the variance these components retain, so this choice
              affects them.
            </p>
          </div>

          <button
            type="button"
            onClick={() => integrateMutation.mutate()}
            disabled={!canRun || integrateMutation.isPending}
            className="mt-4 w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:bg-gray-300"
          >
            {integrateMutation.isPending ? 'Integrating…' : 'Run Integration'}
          </button>

          {!canRun && (
            <p className="mt-2 text-xs text-gray-500">Select two or more datasets to run.</p>
          )}

          {integrateMutation.isError && (
            <p className="mt-3 text-sm text-red-700" role="alert">
              {getApiErrorMessage(integrateMutation.error)}
            </p>
          )}
        </div>
      </div>

      {/* Results */}
      {result && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Integration Results</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="border border-gray-200 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-900 mb-4">Sample Clustering</h3>
              <EmbeddingPlot result={result} />
            </div>

            <div className="border border-gray-200 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-900 mb-4">Omics Contributions</h3>
              {result.contributions.length === 0 && (
                <p className="text-sm text-gray-500">
                  This method does not attribute the result across datasets. The similarity
                  networks are fused into a consensus, and no per-dataset share can be read off
                  it that would hold up, so none is shown.
                </p>
              )}
              <div className="space-y-3">
                {result.contributions.map((entry) => (
                  <div key={entry.dataset_id}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-700">
                        {entry.dataset_name}
                        <span className="ml-2 text-xs text-gray-400">{entry.omics_type}</span>
                      </span>
                      <span className="text-gray-900 font-medium">
                        {formatPercent(entry.contribution)}
                      </span>
                    </div>
                    {/* Bar mirrors the percentage already given in text above. */}
                    <div className="w-full bg-gray-200 rounded-full h-2" aria-hidden="true">
                      <svg
                        className="block h-2 w-full"
                        viewBox="0 0 100 1"
                        preserveAspectRatio="none"
                        role="presentation"
                      >
                        <rect
                          x="0"
                          y="0"
                          width={Math.min(100, Math.max(0, entry.contribution * 100))}
                          height="1"
                          className={OMICS_FILL[entry.omics_type] ?? 'fill-gray-500'}
                        />
                      </svg>
                    </div>
                  </div>
                ))}
              </div>

              {result.contribution_basis === 'scaled_variance_share' && (
                <p className="mt-4 text-xs text-amber-700" role="note">
                  These shares reflect each dataset&apos;s portion of the scaled feature budget, not
                  how much signal it carries. Retain components to get a variance-based attribution.
                </p>
              )}
            </div>
          </div>

          <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 bg-green-50 rounded-lg">
              <p className="text-xs text-green-600 font-medium uppercase">Samples Integrated</p>
              <p className="text-2xl font-semibold text-green-900">{result.n_samples}</p>
              <p className="mt-1 text-xs text-green-700">Shared across all selected datasets</p>
            </div>
            <div className="p-4 bg-blue-50 rounded-lg">
              <p className="text-xs text-blue-600 font-medium uppercase">Features Used</p>
              <p className="text-2xl font-semibold text-blue-900">
                {result.n_features.toLocaleString()}
              </p>
            </div>
            <div className="p-4 bg-purple-50 rounded-lg">
              <p className="text-xs text-purple-600 font-medium uppercase">Variance Explained</p>
              <p className="text-2xl font-semibold text-purple-900">
                {result.variance_explained === null
                  ? 'n/a'
                  : formatPercent(result.variance_explained)}
              </p>
            </div>
            <div className="p-4 bg-orange-50 rounded-lg">
              <p className="text-xs text-orange-600 font-medium uppercase">Clusters Found</p>
              <p className="text-2xl font-semibold text-orange-900">{result.n_clusters}</p>
            </div>
          </div>

          <p className="mt-4 text-xs text-gray-500">
            Method: {result.method}. Contributions attributed by {result.contribution_basis}.
          </p>
        </div>
      )}

      {/* Biomarker Discovery */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="mb-4">
          <h2 className="text-lg font-medium text-gray-900">Biomarker Discovery</h2>
          <p className="text-sm text-gray-500">
            Identify multi-omics biomarkers from the selected datasets
          </p>
        </div>

        <div className="mb-4 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="outcome" className="block text-sm font-medium text-gray-700 mb-1">
              Outcome column
            </label>
            <input
              id="outcome"
              type="text"
              value={outcomeColumn}
              placeholder="e.g. response"
              onChange={(e) => {
                setOutcomeColumn(e.target.value);
                setDiscovery(null);
              }}
              className="block w-full rounded-md border-gray-300 shadow-sm text-sm"
            />
            <p className="mt-1 text-xs text-gray-500">
              A sample annotation to test against. Read from the dataset&apos;s own columns
              first, then from its sample metadata.
            </p>
          </div>

          {analysisType === 'survival' && (
            <div>
              <label htmlFor="event" className="block text-sm font-medium text-gray-700 mb-1">
                Event column
              </label>
              <input
                id="event"
                type="text"
                value={eventColumn}
                placeholder="e.g. deceased"
                onChange={(e) => {
                  setEventColumn(e.target.value);
                  setDiscovery(null);
                }}
                className="block w-full rounded-md border-gray-300 shadow-sm text-sm"
              />
              <p className="mt-1 text-xs text-gray-500">
                1 for an observed event, 0 for censored.
              </p>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 border border-gray-200 rounded-lg">
            <label htmlFor="analysis-type" className="text-sm font-medium text-gray-900 mb-2 block">
              Analysis Type
            </label>
            <select
              id="analysis-type"
              value={analysisType}
              onChange={(e) => {
                setAnalysisType(e.target.value);
                setDiscovery(null);
              }}
              className="block w-full rounded-md border-gray-300 shadow-sm sm:text-sm"
            >
              <option value="differential">Differential Analysis</option>
              <option value="survival">Survival Analysis</option>
            </select>
          </div>
          <div className="p-4 border border-gray-200 rounded-lg">
            <label
              htmlFor="feature-selection"
              className="text-sm font-medium text-gray-900 mb-2 block"
            >
              Feature Selection
            </label>
            <select
              id="feature-selection"
              value={featureSelection}
              onChange={(e) => {
                setFeatureSelection(e.target.value);
                setDiscovery(null);
              }}
              className="block w-full rounded-md border-gray-300 shadow-sm sm:text-sm"
            >
              <option value="stability">Stability Selection</option>
              <option value="lasso">LASSO</option>
              <option value="random_forest">Random Forest</option>
            </select>
          </div>
          <div className="p-4 border border-gray-200 rounded-lg">
            <label htmlFor="cross-validation" className="text-sm font-medium text-gray-900 mb-2 block">
              Cross-Validation
            </label>
            <select
              id="cross-validation"
              value={cvFolds}
              onChange={(e) => {
                setCvFolds(Number(e.target.value));
                setDiscovery(null);
              }}
              className="block w-full rounded-md border-gray-300 shadow-sm sm:text-sm"
            >
              <option value={5}>5-Fold CV</option>
              <option value={10}>10-Fold CV</option>
              <option value={0}>Leave-One-Out</option>
            </select>
          </div>
        </div>

        <button
          type="button"
          onClick={() => discoverMutation.mutate()}
          disabled={!canDiscover || discoverMutation.isPending}
          className="mt-4 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:bg-gray-300"
        >
          {discoverMutation.isPending ? 'Discovering…' : 'Discover Biomarkers'}
        </button>

        {!canDiscover && (
          <p className="mt-2 text-xs text-gray-500">
            Select at least one dataset and name an outcome column to run.
          </p>
        )}

        {discoverMutation.isError && (
          <p className="mt-3 text-sm text-red-700" role="alert">
            {getApiErrorMessage(discoverMutation.error)}
          </p>
        )}

        {discovery && (
          <div className="mt-6">
            <div className="mb-4 grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500 uppercase">Features tested</p>
                <p className="text-xl font-semibold text-gray-900">
                  {discovery.n_features_tested.toLocaleString()}
                </p>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500 uppercase">Significant</p>
                <p className="text-xl font-semibold text-gray-900">{discovery.n_significant}</p>
                <p className="mt-1 text-xs text-gray-500">
                  FDR ≤ {discovery.fdr_threshold}
                </p>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500 uppercase">Selected</p>
                <p className="text-xl font-semibold text-gray-900">{discovery.n_selected}</p>
                <p className="mt-1 text-xs text-gray-500">{discovery.selection_method}</p>
              </div>
              <div className="p-3 bg-emerald-50 rounded-lg">
                <p className="text-xs text-emerald-600 uppercase">Biomarkers</p>
                <p className="text-xl font-semibold text-emerald-900">
                  {discovery.biomarkers.length}
                </p>
                <p className="mt-1 text-xs text-emerald-700">Both, not either</p>
              </div>
            </div>

            {discovery.validation && (
              <p className="mb-4 text-sm text-gray-700">
                {discovery.validation.metric.toUpperCase()}{' '}
                <span className="font-medium">{discovery.validation.score.toFixed(3)}</span>
                {discovery.validation.std !== null && ` ± ${discovery.validation.std.toFixed(3)}`}{' '}
                ({discovery.validation.scheme.replace(/_/g, ' ')}, {discovery.validation.folds}{' '}
                folds)
              </p>
            )}

            {discovery.biomarkers.length > 0 && (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <caption className="sr-only">
                    Biomarkers found, best first
                  </caption>
                  <thead>
                    <tr className="text-left text-xs uppercase text-gray-500">
                      <th scope="col" className="py-2 pr-4">Feature</th>
                      <th scope="col" className="py-2 pr-4">Dataset</th>
                      <th scope="col" className="py-2 pr-4">Effect</th>
                      <th scope="col" className="py-2 pr-4">q-value</th>
                      <th scope="col" className="py-2">Selection</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {discovery.biomarkers.map((marker) => (
                      <tr key={`${marker.dataset_id}-${marker.feature}`}>
                        <td className="py-2 pr-4 font-medium text-gray-900">{marker.feature}</td>
                        <td className="py-2 pr-4 text-gray-600">
                          {marker.dataset_name}
                          <span className="ml-2 text-xs text-gray-400">{marker.omics_type}</span>
                        </td>
                        <td className="py-2 pr-4 text-gray-900">{marker.effect.toFixed(2)}</td>
                        <td className="py-2 pr-4 text-gray-900">{marker.q_value.toExponential(2)}</td>
                        <td className="py-2 text-gray-900">
                          {marker.selection_score.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {discovery.notes.length > 0 && (
              <ul className="mt-4 space-y-1 text-xs text-gray-500" role="note">
                {discovery.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
