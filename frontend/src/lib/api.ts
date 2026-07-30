/**
 * API client
 * ==========
 *
 * Thin, typed wrapper around the REST API (mounted at ``/api/v1``). A single
 * axios instance attaches the persisted bearer token and normalises errors so
 * callers can render a friendly message via {@link getApiErrorMessage}.
 */

import axios, { AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios';

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

export interface User {
  id: string;
  email: string;
  username?: string | null;
  full_name?: string | null;
  organization?: string | null;
  bio?: string | null;
  is_active?: boolean;
  is_verified?: boolean;
  roles?: string[];
  settings?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
  last_login?: string | null;
}

export interface Project {
  id: string;
  name: string;
  description?: string | null;
  project_type: string;
  omics_types: string[];
  tags: string[];
  visibility: string;
  status: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface DatasetSummary {
  id: string;
  name: string;
  omics_type: string;
  status: string;
  sample_count: number | null;
  feature_count: number | null;
  source?: string | null;
  created_at: string;
}

/** One omics block's share of the integrated signal. */
export interface OmicsContribution {
  dataset_id: string;
  dataset_name: string;
  omics_type: string;
  /** Share of the integrated signal, 0-1. */
  contribution: number;
}

/** A sample positioned in the first two dimensions of the fused space. */
export interface IntegrationSamplePoint {
  sample: string;
  x: number;
  y: number;
  cluster: number;
}

export interface IntegrationResult {
  method: string;
  n_samples: number;
  n_features: number;
  n_omics: number;
  /** Share of variance retained by the fused representation, 0-1. */
  variance_explained: number | null;
  /**
   * How `contribution` was derived. `pca_loadings` attributes retained variance
   * through component loadings. `scaled_variance_share` is only a feature-count
   * proxy and must not be presented as a measure of signal.
   */
  contribution_basis: string;
  contributions: OmicsContribution[];
  n_clusters: number;
  embedding: IntegrationSamplePoint[];
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type?: string;
  user?: User | null;
}

export interface MlModelInfo {
  name: string;
  type?: string;
  task?: string;
  description?: string;
  [key: string]: unknown;
}

export interface TrainResponse {
  task_id: string;
  message?: string;
  status?: string;
}

export interface TaskStatus {
  task_id: string;
  status: string;
  ready: boolean;
  result?: unknown;
  error?: string;
}

interface ListParams {
  page?: number;
  page_size?: number;
}

interface DatasetListParams extends ListParams {
  project_id?: string;
}

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------

const API_BASE: string =
  (import.meta.env.VITE_API_URL as string | undefined) ?? '/api/v1';

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

/** Read the persisted access token written by the Zustand auth store. */
function getAccessToken(): string | null {
  try {
    const raw = localStorage.getItem('auth-storage');
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { state?: { accessToken?: string | null } };
    return parsed.state?.accessToken ?? null;
  } catch {
    return null;
  }
}

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/** Turn any thrown value into a human-readable message. */
export function getApiErrorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    const data = error.response?.data as { detail?: unknown; message?: unknown } | undefined;
    const detail = data?.detail ?? data?.message;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown };
      if (first && typeof first.msg === 'string') return first.msg;
    }
    if (error.message) return error.message;
  }
  if (error instanceof Error) return error.message;
  return 'An unexpected error occurred';
}

// ---------------------------------------------------------------------------
// Endpoint groups
// ---------------------------------------------------------------------------

export const endpoints = {
  auth: {
    async login(payload: { email: string; password: string }): Promise<AuthResponse> {
      // The token endpoint expects OAuth2 form fields (``username``/``password``).
      const form = new URLSearchParams();
      form.append('username', payload.email);
      form.append('password', payload.password);
      const { data } = await apiClient.post<AuthResponse>('/auth/login', form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });
      return data;
    },
    async register(payload: {
      email: string;
      password: string;
      full_name: string;
    }): Promise<AuthResponse> {
      const { data } = await apiClient.post<AuthResponse>('/auth/register', payload);
      return data;
    },
    async logout(): Promise<void> {
      await apiClient.post('/auth/logout');
    },
    async me(): Promise<User> {
      const { data } = await apiClient.get<User>('/auth/me');
      return data;
    },
  },
};

export const projects = {
  async list(params: ListParams = {}): Promise<Paginated<Project>> {
    const { data } = await apiClient.get<Paginated<Project>>('/projects/', { params });
    return data;
  },
  async create(payload: { name: string; description?: string }): Promise<Project> {
    const { data } = await apiClient.post<Project>('/projects/', payload);
    return data;
  },
};

export const datasets = {
  async list(params: DatasetListParams = {}): Promise<Paginated<DatasetSummary>> {
    const { data } = await apiClient.get<Paginated<DatasetSummary>>('/datasets/', { params });
    return data;
  },
  async upload(datasetId: string, file: File): Promise<unknown> {
    const form = new FormData();
    form.append('file', file);
    const { data } = await apiClient.post<unknown>(`/datasets/${datasetId}/upload`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },
};

export const omics = {
  /** Run a multi-omics integration over stored datasets and return the result. */
  async integrate(payload: {
    project_id: string;
    dataset_ids: string[];
    method: string;
    n_components?: number;
    /** GMT file of pathway definitions; required by pathway_integration. */
    pathway_file?: string;
  }): Promise<IntegrationResult> {
    const { data } = await apiClient.post<IntegrationResult>('/omics/integrate', payload);
    return data;
  },
};

export const ml = {
  async listModels(): Promise<MlModelInfo[]> {
    const { data } = await apiClient.get<MlModelInfo[]>('/ml/models');
    return data;
  },
  async train(payload: {
    model_type: string;
    dataset_ids: string[];
    target_column: string;
    parameters: Record<string, unknown>;
    cross_validation?: boolean;
    cv_folds?: number;
    test_size?: number;
  }): Promise<TrainResponse> {
    const { data } = await apiClient.post<TrainResponse>('/ml/train', payload);
    return data;
  },
  async taskStatus(taskId: string): Promise<TaskStatus> {
    const { data } = await apiClient.get<TaskStatus>(`/ml/task/${taskId}`);
    return data;
  },
};

export const tools = {
  async listGenePredictors(): Promise<unknown> {
    const { data } = await apiClient.get<unknown>('/tools/annotation/genes/predictors');
    return data;
  },
  async predictGenes(payload: {
    sequence: string;
    contig_id: string;
    predictor: string;
    include_sequences: boolean;
  }): Promise<unknown> {
    const { data } = await apiClient.post<unknown>('/tools/annotation/genes/predict', payload);
    return data;
  },
  async runMd(payload: {
    pdb: string;
    n_steps: number;
    save_interval: number;
    minimize_steps: number;
  }): Promise<unknown> {
    const { data } = await apiClient.post<unknown>('/tools/chemistry/md/run', payload);
    return data;
  },
  async structureMdDock(payload: {
    protein_pdb: string;
    ligand_pdb: string;
    md_steps: number;
    docking_poses: number;
  }): Promise<unknown> {
    const { data } = await apiClient.post<unknown>(
      '/tools/chemistry/pipelines/structure-md-dock',
      payload,
    );
    return data;
  },
};

export default apiClient;
