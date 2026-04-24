/**
 * Datasets Page - Connected to REST API
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { datasets as datasetsApi, projects as projectsApi, type DatasetSummary, type Project } from '../lib/api';
import { useAuthStore } from '../stores/auth';

export default function Datasets() {
  const queryClient = useQueryClient();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [uploadDatasetId, setUploadDatasetId] = useState<string | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  const { data: projectsData } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.list({ page: 1, page_size: 100 }),
    enabled: isAuthenticated,
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ['datasets', selectedProjectId],
    queryFn: () => datasetsApi.list({
      project_id: selectedProjectId ?? undefined,
      page: 1,
      page_size: 50,
    }),
    enabled: isAuthenticated,
  });

  const uploadMutation = useMutation({
    mutationFn: ({ datasetId, file }: { datasetId: string; file: File }) =>
      datasetsApi.upload(datasetId, file),
    onSuccess: (_, { datasetId }) => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
      setUploadDatasetId(null);
      setUploadFile(null);
      toast.success(`Upload started for dataset ${datasetId}`);
    },
    onError: (err: unknown) => {
      const msg = err && typeof err === 'object' && 'message' in err ? String((err as Error).message) : 'Upload failed';
      toast.error(msg);
    },
  });

  const items = data?.items ?? [];
  const projects = projectsData?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Datasets</h1>
          <p className="mt-1 text-sm text-gray-500">Upload and manage your omics datasets</p>
        </div>
      </div>

      {isAuthenticated && projects.length > 0 && (
        <div className="flex items-center gap-2">
          <label htmlFor="project-filter" className="text-sm font-medium text-gray-700">Project:</label>
          <select
            id="project-filter"
            value={selectedProjectId ?? ''}
            onChange={(e) => setSelectedProjectId(e.target.value || null)}
            className="rounded-md border-gray-300 shadow-sm sm:text-sm"
          >
            <option value="">All projects</option>
            {projects.map((p: Project) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
      )}

      {uploadDatasetId && (
        <div className="bg-white shadow rounded-lg p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Upload file</h3>
          <input
            type="file"
            accept=".csv,.tsv,.parquet,.vcf,.maf,.gct"
            aria-label="Choose dataset file to upload"
            onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
          />
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              disabled={!uploadFile || uploadMutation.isPending}
              onClick={() => uploadFile && uploadMutation.mutate({ datasetId: uploadDatasetId, file: uploadFile })}
              className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              {uploadMutation.isPending ? 'Uploading…' : 'Upload'}
            </button>
            <button
              type="button"
              onClick={() => { setUploadDatasetId(null); setUploadFile(null); }}
              className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="bg-white shadow rounded-lg p-6 text-center text-gray-500">Loading datasets…</div>
      )}
      {error && (
        <div className="bg-white shadow rounded-lg p-6 text-center text-red-600">
          Failed to load datasets. Sign in or check the API.
        </div>
      )}
      {!isLoading && !error && items.length === 0 && (
        <div className="bg-white shadow rounded-lg p-6 text-center text-gray-500">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No datasets</h3>
          <p className="mt-1 text-sm text-gray-500">Create a dataset from a project, then upload a file.</p>
        </div>
      )}
      {!isLoading && !error && items.length > 0 && (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <ul className="divide-y divide-gray-200">
            {items.map((d: DatasetSummary) => (
              <li key={d.id} className="px-6 py-4 hover:bg-gray-50 flex justify-between items-center">
                <div>
                  <p className="text-sm font-medium text-gray-900">{d.name}</p>
                  <p className="text-xs text-gray-500">
                    {d.omics_type} · {d.status}
                    {d.sample_count != null && ` · ${d.sample_count} samples`}
                    {d.feature_count != null && ` · ${d.feature_count} features`}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setUploadDatasetId(d.id)}
                  className="text-sm text-indigo-600 hover:text-indigo-800"
                >
                  Upload file
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
