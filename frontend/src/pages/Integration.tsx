/**
 * Multi-Omics Integration Page
 */

import { useState } from 'react';

const integrationMethods = [
  {
    id: 'early_fusion',
    name: 'Early Fusion',
    description: 'Concatenate features from multiple omics datasets before analysis',
    category: 'Data Fusion',
  },
  {
    id: 'intermediate_fusion',
    name: 'Intermediate Fusion',
    description: 'Joint dimensionality reduction of multiple omics datasets',
    category: 'Data Fusion',
  },
  {
    id: 'late_fusion',
    name: 'Late Fusion',
    description: 'Combine predictions from individual omics models',
    category: 'Data Fusion',
  },
  {
    id: 'snf',
    name: 'Similarity Network Fusion',
    description: 'Fuse patient similarity networks from different omics',
    category: 'Network-based',
  },
  {
    id: 'network_integration',
    name: 'Network Integration',
    description: 'Build and integrate co-expression networks',
    category: 'Network-based',
  },
  {
    id: 'pathway_integration',
    name: 'Pathway-level Integration',
    description: 'Integrate data at the pathway/gene set level',
    category: 'Pathway-based',
  },
];

const omicsTypes = [
  { id: 'transcriptomics', name: 'Transcriptomics', color: 'bg-blue-500' },
  { id: 'proteomics', name: 'Proteomics', color: 'bg-green-500' },
  { id: 'metabolomics', name: 'Metabolomics', color: 'bg-purple-500' },
  { id: 'genomics', name: 'Genomics', color: 'bg-red-500' },
  { id: 'epigenomics', name: 'Epigenomics', color: 'bg-yellow-500' },
  { id: 'lipidomics', name: 'Lipidomics', color: 'bg-pink-500' },
];

const BG_TO_FILL: Record<string, string> = {
  'bg-blue-500': 'fill-blue-500',
  'bg-green-500': 'fill-green-500',
  'bg-purple-500': 'fill-purple-500',
  'bg-red-500': 'fill-red-500',
  'bg-yellow-500': 'fill-yellow-500',
  'bg-pink-500': 'fill-pink-500',
};

export default function Integration() {
  const [selectedOmics, setSelectedOmics] = useState<string[]>([]);
  const [selectedMethod, setSelectedMethod] = useState('');
  const [integrationStatus, setIntegrationStatus] = useState<'idle' | 'running' | 'complete'>('idle');

  const toggleOmics = (omicsId: string) => {
    setSelectedOmics((prev) =>
      prev.includes(omicsId) ? prev.filter((id) => id !== omicsId) : [...prev, omicsId]
    );
  };

  const handleRunIntegration = () => {
    setIntegrationStatus('running');
    setTimeout(() => setIntegrationStatus('complete'), 3000);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Multi-Omics Integration</h1>
        <p className="mt-1 text-sm text-gray-500">
          Integrate multiple omics datasets for comprehensive analysis
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Dataset Selection */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Select Omics Datasets</h2>
          
          <div className="space-y-3">
            {omicsTypes.map((omics) => (
              <label
                key={omics.id}
                className={`flex items-center p-3 border rounded-lg cursor-pointer transition-all ${
                  selectedOmics.includes(omics.id)
                    ? 'border-indigo-500 bg-indigo-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedOmics.includes(omics.id)}
                  onChange={() => toggleOmics(omics.id)}
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 rounded"
                />
                <div className="ml-3 flex items-center">
                  <span className={`w-3 h-3 rounded-full ${omics.color} mr-2`}></span>
                  <span className="text-sm font-medium text-gray-900">{omics.name}</span>
                </div>
              </label>
            ))}
          </div>

          <div className="mt-4 pt-4 border-t border-gray-200">
            <p className="text-sm text-gray-500">
              {selectedOmics.length} dataset{selectedOmics.length !== 1 ? 's' : ''} selected
            </p>
          </div>
        </div>

        {/* Integration Method */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Integration Method</h2>
          
          <div className="space-y-3">
            {['Data Fusion', 'Network-based', 'Pathway-based'].map((category) => (
              <div key={category}>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  {category}
                </p>
                {integrationMethods
                  .filter((m) => m.category === category)
                  .map((method) => (
                    <label
                      key={method.id}
                      className={`block p-3 border rounded-lg cursor-pointer transition-all mb-2 ${
                        selectedMethod === method.id
                          ? 'border-indigo-500 bg-indigo-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-start">
                        <input
                          type="radio"
                          name="method"
                          value={method.id}
                          checked={selectedMethod === method.id}
                          onChange={(e) => setSelectedMethod(e.target.value)}
                          className="h-4 w-4 mt-0.5 text-indigo-600 focus:ring-indigo-500"
                        />
                        <div className="ml-3">
                          <p className="text-sm font-medium text-gray-900">{method.name}</p>
                          <p className="text-xs text-gray-500">{method.description}</p>
                        </div>
                      </div>
                    </label>
                  ))}
              </div>
            ))}
          </div>
        </div>

        {/* Parameters & Run */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Parameters</h2>
          
          <div className="space-y-4">
            <div>
              <label htmlFor="num-components" className="block text-sm font-medium text-gray-700">
                Number of Components
              </label>
              <input
                id="num-components"
                type="number"
                defaultValue={10}
                min={2}
                max={100}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              />
            </div>

            <div>
              <label htmlFor="scaling-method" className="block text-sm font-medium text-gray-700">
                Scaling Method
              </label>
              <select id="scaling-method" className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
                <option value="standard">Standard Scaling</option>
                <option value="minmax">Min-Max Scaling</option>
                <option value="robust">Robust Scaling</option>
              </select>
            </div>

            {selectedMethod === 'snf' && (
              <>
                <div>
                  <label htmlFor="num-neighbors" className="block text-sm font-medium text-gray-700">
                    Number of Neighbors (K)
                  </label>
                  <input
                    id="num-neighbors"
                    type="number"
                    defaultValue={20}
                    min={5}
                    max={50}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  />
                </div>
                <div>
                  <label htmlFor="iterations" className="block text-sm font-medium text-gray-700">
                    Iterations
                  </label>
                  <input
                    id="iterations"
                    type="number"
                    defaultValue={20}
                    min={5}
                    max={100}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  />
                </div>
              </>
            )}

            <button
              onClick={handleRunIntegration}
              disabled={selectedOmics.length < 2 || !selectedMethod || integrationStatus === 'running'}
              className="w-full py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {integrationStatus === 'running' ? 'Integrating...' : 'Run Integration'}
            </button>

            {integrationStatus === 'running' && (
              <div className="p-4 bg-blue-50 rounded-lg">
                <div className="flex items-center">
                  <svg className="animate-spin h-5 w-5 text-blue-600 mr-2" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                  </svg>
                  <span className="text-sm text-blue-700">Running integration...</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Results Section */}
      {integrationStatus === 'complete' && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Integration Results</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Integrated View */}
            <div className="border border-gray-200 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-900 mb-4">Sample Clustering</h3>
              <div className="h-64 bg-gray-100 rounded flex items-center justify-center">
                <div className="text-center">
                  <svg className="w-12 h-12 text-gray-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  <span className="text-sm text-gray-500">t-SNE/UMAP visualization</span>
                </div>
              </div>
            </div>

            {/* Feature Contributions */}
            <div className="border border-gray-200 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-900 mb-4">Omics Contributions</h3>
              <div className="space-y-3">
                {selectedOmics.map((omicsId) => {
                  const omics = omicsTypes.find((o) => o.id === omicsId);
                  // PLACEHOLDER, NOT A COMPUTED RESULT. This page performs no
                  // integration: handleRunIntegration only waits 3s before
                  // flipping to 'complete', and nothing here calls the API. The
                  // percentage below is a random number and changes on every
                  // re-render. It must be replaced with a real contribution
                  // from the integration endpoint before this screen is used to
                  // interpret data.
                  // eslint-disable-next-line react-hooks/purity -- see above
                  const contribution = Math.random() * 40 + 10;
                  return (
                    <div key={omicsId}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-700">{omics?.name}</span>
                        <span className="text-gray-900 font-medium">{contribution.toFixed(1)}%</span>
                      </div>
                      {/* Visual progress bar - percentage is already conveyed in text above */}
                      <div className="w-full bg-gray-200 rounded-full h-2" aria-hidden="true">
                        <svg
                          className="block h-2 w-full text-gray-200"
                          viewBox="0 0 100 1"
                          preserveAspectRatio="none"
                          role="presentation"
                        >
                          <rect
                            x="0"
                            y="0"
                            width={Math.min(100, Math.max(0, contribution))}
                            height="1"
                            className={omics?.color ? BG_TO_FILL[omics.color] ?? 'fill-gray-500' : 'fill-gray-500'}
                          />
                        </svg>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 bg-green-50 rounded-lg">
              <p className="text-xs text-green-600 font-medium uppercase">Samples Integrated</p>
              <p className="text-2xl font-semibold text-green-900">256</p>
            </div>
            <div className="p-4 bg-blue-50 rounded-lg">
              <p className="text-xs text-blue-600 font-medium uppercase">Features Used</p>
              <p className="text-2xl font-semibold text-blue-900">12,458</p>
            </div>
            <div className="p-4 bg-purple-50 rounded-lg">
              <p className="text-xs text-purple-600 font-medium uppercase">Variance Explained</p>
              <p className="text-2xl font-semibold text-purple-900">78.4%</p>
            </div>
            <div className="p-4 bg-orange-50 rounded-lg">
              <p className="text-xs text-orange-600 font-medium uppercase">Clusters Found</p>
              <p className="text-2xl font-semibold text-orange-900">4</p>
            </div>
          </div>
        </div>
      )}

      {/* Biomarker Discovery */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-medium text-gray-900">Biomarker Discovery</h2>
            <p className="text-sm text-gray-500">
              Identify multi-omics biomarkers from integrated data
            </p>
          </div>
          <button
            disabled={integrationStatus !== 'complete'}
            className="px-4 py-2 text-sm font-medium text-white bg-emerald-600 rounded-lg hover:bg-emerald-700 disabled:bg-gray-400"
          >
            Discover Biomarkers
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 border border-gray-200 rounded-lg">
            <label htmlFor="analysis-type" className="text-sm font-medium text-gray-900 mb-2 block">Analysis Type</label>
            <select id="analysis-type" className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
              <option>Differential Analysis</option>
              <option>Survival Analysis</option>
              <option>Classification</option>
            </select>
          </div>
          <div className="p-4 border border-gray-200 rounded-lg">
            <label htmlFor="feature-selection" className="text-sm font-medium text-gray-900 mb-2 block">Feature Selection</label>
            <select id="feature-selection" className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
              <option>Stability Selection</option>
              <option>LASSO</option>
              <option>Random Forest</option>
            </select>
          </div>
          <div className="p-4 border border-gray-200 rounded-lg">
            <label htmlFor="cross-validation" className="text-sm font-medium text-gray-900 mb-2 block">Cross-Validation</label>
            <select id="cross-validation" className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
              <option>5-Fold CV</option>
              <option>10-Fold CV</option>
              <option>Leave-One-Out</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );
}
