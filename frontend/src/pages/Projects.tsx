/**
 * Projects Page - Connected to REST API
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { projects as projectsApi, type Project } from '../lib/api';
import { useAuthStore } from '../stores/auth';

export default function Projects() {
  const queryClient = useQueryClient();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.list({ page: 1, page_size: 50 }),
    enabled: isAuthenticated,
  });

  const createMutation = useMutation({
    mutationFn: (payload: { name: string; description?: string }) => projectsApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setShowCreate(false);
      setName('');
      setDescription('');
      toast.success('Project created');
    },
    onError: (err: unknown) => {
      const msg = err && typeof err === 'object' && 'message' in err ? String((err as Error).message) : 'Failed to create project';
      toast.error(msg);
    },
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
          <p className="mt-1 text-sm text-gray-500">Manage your multi-omics analysis projects</p>
        </div>
        {isAuthenticated && (
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            New Project
          </button>
        )}
      </div>

      {showCreate && (
        <div className="bg-white shadow rounded-lg p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Create project</h3>
          <div className="space-y-4">
            <div>
              <label htmlFor="project-name" className="block text-sm font-medium text-gray-700">Name</label>
              <input
                id="project-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm sm:text-sm"
              />
            </div>
            <div>
              <label htmlFor="project-desc" className="block text-sm font-medium text-gray-700">Description</label>
              <textarea
                id="project-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm sm:text-sm"
              />
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => createMutation.mutate({ name, description: description || undefined })}
                disabled={!name.trim() || createMutation.isPending}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
              >
                {createMutation.isPending ? 'Creating…' : 'Create'}
              </button>
              <button
                type="button"
                onClick={() => { setShowCreate(false); setName(''); setDescription(''); }}
                className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="bg-white shadow rounded-lg p-6 text-center text-gray-500">Loading projects…</div>
      )}
      {error && (
        <div className="bg-white shadow rounded-lg p-6 text-center text-red-600">
          Failed to load projects. Sign in or check the API.
        </div>
      )}
      {!isLoading && !error && items.length === 0 && (
        <div className="bg-white shadow rounded-lg">
          <div className="p-6 text-center text-gray-500">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">No projects</h3>
            <p className="mt-1 text-sm text-gray-500">Get started by creating a new project.</p>
          </div>
        </div>
      )}
      {!isLoading && !error && items.length > 0 && (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <ul className="divide-y divide-gray-200">
            {items.map((p: Project) => (
              <li key={p.id} className="px-6 py-4 hover:bg-gray-50">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{p.name}</p>
                    {p.description && <p className="text-sm text-gray-500 mt-0.5">{p.description}</p>}
                    <p className="text-xs text-gray-400 mt-1">Status: {p.status} · Updated {new Date(p.updated_at).toLocaleDateString()}</p>
                  </div>
                </div>
              </li>
            ))}
          </ul>
          {total > items.length && (
            <p className="px-6 py-2 text-sm text-gray-500">Showing {items.length} of {total} projects</p>
          )}
        </div>
      )}
    </div>
  );
}
