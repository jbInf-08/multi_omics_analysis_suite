/**
 * Generic Omics Module Page
 */

import { useParams } from 'react-router-dom';

export default function OmicsModule() {
  const { omicsType } = useParams<{ omicsType: string }>();
  const displayName = omicsType 
    ? omicsType.charAt(0).toUpperCase() + omicsType.slice(1) 
    : 'Unknown';

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{displayName} Analysis</h1>
        <p className="mt-1 text-sm text-gray-500">
          Analyze {omicsType ?? 'omics'} data with specialized pipelines and visualizations
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Analysis Options */}
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Available Analyses</h2>
            <div className="grid grid-cols-2 gap-4">
              {['Quality Control', 'Normalization', 'Differential Analysis', 'Pathway Analysis', 
                'Network Analysis', 'Visualization'].map((analysis) => (
                <button
                  key={analysis}
                  className="text-left p-4 border rounded-lg hover:border-indigo-500 hover:bg-indigo-50"
                >
                  <h3 className="font-medium text-gray-900">{analysis}</h3>
                  <p className="text-sm text-gray-500">Run {analysis.toLowerCase()}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Results Placeholder */}
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Results</h2>
            <div className="h-64 bg-gray-50 rounded-lg flex items-center justify-center text-gray-400">
              <span>Select an analysis to view results</span>
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <div className="bg-white shadow rounded-lg p-6">
            <label htmlFor="dataset-select" className="text-lg font-medium text-gray-900 mb-4 block">Data Selection</label>
            <select id="dataset-select" className="w-full border-gray-300 rounded-md shadow-sm">
              <option>Select a dataset...</option>
            </select>
          </div>

          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Parameters</h2>
            <p className="text-sm text-gray-500">
              Configure analysis parameters after selecting a dataset
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
