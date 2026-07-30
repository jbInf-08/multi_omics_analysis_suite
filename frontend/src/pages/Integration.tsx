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
  datasets as datasetsApi,
  getApiErrorMessage,
  omics as omicsApi,
  projects as projectsApi,
  type IntegrationResult,
} from '../lib/api';
import { useAuthStore } from '../stores/auth';

/**
 * Only methods the API implements. The list previously advertised six,
 * including three that no endpoint backed; offering them here would produce a
 * 400 the moment a user picked one.
 */
const integrationMethods = [
  {
    id: 'intermediate_fusion',
    name: 'Intermediate Fusion',
    description: 'Joint dimensionality reduction across the selected datasets',
    category: 'Data Fusion',
  },
  {
    id: 'early_fusion',
    name: 'Early Fusion',
    description: 'Concatenate scaled features, then reduce jointly',
    category: 'Data Fusion',
  },
];

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
        First two components of the fused space. Colour indicates the cluster assigned by k-means,
        with k chosen by silhouette score.
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

  const toggleDataset = (datasetId: string) => {
    setSelectedDatasetIds((prev) =>
      prev.includes(datasetId) ? prev.filter((id) => id !== datasetId) : [...prev, datasetId]
    );
    setResult(null);
  };

  const canRun = selectedDatasetIds.length >= 2 && Boolean(selectedMethod);

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
                </span>
              </label>
            ))}
          </fieldset>

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

              {result.contribution_basis !== 'pca_loadings' && (
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

      {/*
        Biomarker Discovery is not implemented. The button has never had a
        handler and the three selects have never had state, so the controls did
        nothing when they appeared enabled. Kept, but disabled and labelled,
        rather than removed: whether to build it or drop it is a product call,
        and either way it should not look operable in the meantime.
      */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-medium text-gray-900">Biomarker Discovery</h2>
            <p className="text-sm text-gray-500">
              Identify multi-omics biomarkers from integrated data
            </p>
          </div>
          <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-600">
            Not yet available
          </span>
        </div>

        <p className="mb-4 text-sm text-gray-500">
          This step is not wired to an endpoint yet, so the controls below are disabled.
        </p>

        <fieldset disabled className="grid grid-cols-1 md:grid-cols-3 gap-4 opacity-60">
          <legend className="sr-only">Biomarker discovery options (unavailable)</legend>
          <div className="p-4 border border-gray-200 rounded-lg">
            <label htmlFor="analysis-type" className="text-sm font-medium text-gray-900 mb-2 block">
              Analysis Type
            </label>
            <select
              id="analysis-type"
              className="block w-full rounded-md border-gray-300 shadow-sm sm:text-sm"
            >
              <option>Differential Analysis</option>
              <option>Survival Analysis</option>
              <option>Classification</option>
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
              className="block w-full rounded-md border-gray-300 shadow-sm sm:text-sm"
            >
              <option>Stability Selection</option>
              <option>LASSO</option>
              <option>Random Forest</option>
            </select>
          </div>
          <div className="p-4 border border-gray-200 rounded-lg">
            <label
              htmlFor="cross-validation"
              className="text-sm font-medium text-gray-900 mb-2 block"
            >
              Cross-Validation
            </label>
            <select
              id="cross-validation"
              className="block w-full rounded-md border-gray-300 shadow-sm sm:text-sm"
            >
              <option>5-Fold CV</option>
              <option>10-Fold CV</option>
              <option>Leave-One-Out</option>
            </select>
          </div>
        </fieldset>
      </div>
    </div>
  );
}
