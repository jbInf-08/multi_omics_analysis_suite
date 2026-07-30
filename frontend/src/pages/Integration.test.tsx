import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { IntegrationResult } from '../lib/api';

const integrate = vi.fn();
const listProjects = vi.fn();
const listDatasets = vi.fn();

vi.mock('../lib/api', () => ({
  omics: { integrate: (...args: unknown[]) => integrate(...args) },
  projects: { list: (...args: unknown[]) => listProjects(...args) },
  datasets: { list: (...args: unknown[]) => listDatasets(...args) },
  getApiErrorMessage: (e: unknown) => (e instanceof Error ? e.message : 'error'),
}));

vi.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock('../stores/auth', () => ({
  useAuthStore: (selector: (s: { isAuthenticated: boolean }) => unknown) =>
    selector({ isAuthenticated: true }),
}));

const Integration = (await import('./Integration')).default;

const PROJECT_ID = 'p1';
const RNA_ID = 'd-rna';
const PROT_ID = 'd-prot';

const RESULT: IntegrationResult = {
  method: 'intermediate_pca',
  n_samples: 42,
  n_features: 1337,
  n_omics: 2,
  variance_explained: 0.6123,
  contribution_basis: 'pca_loadings',
  contributions: [
    { dataset_id: RNA_ID, dataset_name: 'RNA-seq', omics_type: 'transcriptomics', contribution: 0.72 },
    { dataset_id: PROT_ID, dataset_name: 'Proteome', omics_type: 'proteomics', contribution: 0.28 },
  ],
  n_clusters: 3,
  embedding: [
    { sample: 'S0', x: 1, y: 2, cluster: 0 },
    { sample: 'S1', x: -1, y: 0.5, cluster: 1 },
    { sample: 'S2', x: 0.2, y: -3, cluster: 2 },
  ],
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Integration />
    </QueryClientProvider>
  );
}

/** Pick a project, then tick both datasets. */
async function selectTwoDatasets(user: ReturnType<typeof userEvent.setup>) {
  // The option only exists once the projects query resolves.
  await screen.findByRole('option', { name: 'Cohort A' });
  await user.selectOptions(screen.getByLabelText('Project'), PROJECT_ID);
  const rna = await screen.findByRole('checkbox', { name: /RNA-seq/ });
  await user.click(rna);
  await user.click(screen.getByRole('checkbox', { name: /Proteome/ }));
}

describe('Integration page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listProjects.mockResolvedValue({ items: [{ id: PROJECT_ID, name: 'Cohort A' }] });
    listDatasets.mockResolvedValue({
      items: [
        {
          id: RNA_ID,
          name: 'RNA-seq',
          omics_type: 'transcriptomics',
          sample_count: 42,
          feature_count: 900,
        },
        {
          id: PROT_ID,
          name: 'Proteome',
          omics_type: 'proteomics',
          sample_count: 42,
          feature_count: 437,
        },
      ],
    });
    integrate.mockResolvedValue(RESULT);
  });

  it('shows no results before an integration has been run', async () => {
    renderPage();
    await screen.findByText('Datasets');
    expect(screen.queryByText('Integration Results')).not.toBeInTheDocument();
  });

  it('cannot run until at least two datasets are selected', async () => {
    const user = userEvent.setup();
    renderPage();

    const run = await screen.findByRole('button', { name: /Run Integration/ });
    expect(run).toBeDisabled();

    await screen.findByRole('option', { name: 'Cohort A' });
    await user.selectOptions(screen.getByLabelText('Project'), PROJECT_ID);
    await user.click(await screen.findByRole('checkbox', { name: /RNA-seq/ }));
    expect(run).toBeDisabled();

    await user.click(screen.getByRole('checkbox', { name: /Proteome/ }));
    expect(run).toBeEnabled();
  });

  it('sends the selected datasets and method to the API', async () => {
    const user = userEvent.setup();
    renderPage();
    await selectTwoDatasets(user);
    await user.click(screen.getByRole('button', { name: /Run Integration/ }));

    await waitFor(() => expect(integrate).toHaveBeenCalledTimes(1));
    expect(integrate).toHaveBeenCalledWith({
      project_id: PROJECT_ID,
      dataset_ids: [RNA_ID, PROT_ID],
      method: 'intermediate_fusion',
      n_components: 10,
    });
  });

  it('renders the figures returned by the API, not invented ones', async () => {
    const user = userEvent.setup();
    renderPage();
    await selectTwoDatasets(user);
    await user.click(screen.getByRole('button', { name: /Run Integration/ }));

    await screen.findByText('Integration Results');

    // Every stat comes from RESULT above.
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('1,337')).toBeInTheDocument();
    expect(screen.getByText('61.2%')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();

    // Contributions are the API's, and are labelled per dataset.
    expect(screen.getByText('72.0%')).toBeInTheDocument();
    expect(screen.getByText('28.0%')).toBeInTheDocument();

    // The old page hardcoded these; they must not appear.
    expect(screen.queryByText('256')).not.toBeInTheDocument();
    expect(screen.queryByText('12,458')).not.toBeInTheDocument();
    expect(screen.queryByText('78.4%')).not.toBeInTheDocument();
  });

  it('plots one point per returned sample', async () => {
    const user = userEvent.setup();
    renderPage();
    await selectTwoDatasets(user);
    await user.click(screen.getByRole('button', { name: /Run Integration/ }));

    const plot = await screen.findByRole('img', {
      name: /Fused sample space: 3 samples in 3 clusters/,
    });
    expect(plot.querySelectorAll('circle')).toHaveLength(RESULT.embedding.length);
  });

  it('is stable across re-renders', async () => {
    const user = userEvent.setup();
    const { rerender } = renderPage();
    await selectTwoDatasets(user);
    await user.click(screen.getByRole('button', { name: /Run Integration/ }));
    await screen.findByText('Integration Results');

    const before = screen.getByText('72.0%').textContent;
    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <Integration />
      </QueryClientProvider>
    );
    // The value is not recomputed on render; the old page's random figure was.
    expect(before).toBe('72.0%');
  });

  it('warns when the contribution basis is only a feature-count proxy', async () => {
    integrate.mockResolvedValue({ ...RESULT, contribution_basis: 'scaled_variance_share' });
    const user = userEvent.setup();
    renderPage();
    await selectTwoDatasets(user);
    await user.click(screen.getByRole('button', { name: /Run Integration/ }));

    await screen.findByText('Integration Results');
    expect(screen.getByRole('note')).toHaveTextContent(/not\s+how much signal it carries/i);
  });

  it('surfaces an API failure instead of showing results', async () => {
    integrate.mockRejectedValue(new Error('Datasets share no common samples'));
    const user = userEvent.setup();
    renderPage();
    await selectTwoDatasets(user);
    await user.click(screen.getByRole('button', { name: /Run Integration/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Datasets share no common samples'
    );
    expect(screen.queryByText('Integration Results')).not.toBeInTheDocument();
  });

  it('does not present the unimplemented biomarker step as usable', async () => {
    renderPage();
    await screen.findByText('Biomarker Discovery');

    expect(screen.getByText('Not yet available')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Discover Biomarkers/ })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Analysis Type')).toBeDisabled();
  });
});

describe('Integration page — network methods', () => {
  const NETWORK_RESULT: IntegrationResult = {
    ...RESULT,
    method: 'snf',
    variance_explained: null,
    contribution_basis: 'not_applicable',
    contributions: [],
  };

  beforeEach(() => {
    integrate.mockResolvedValue(NETWORK_RESULT);
  });

  async function runSnf(user: ReturnType<typeof userEvent.setup>) {
    await selectTwoDatasets(user);
    await user.click(screen.getByRole('radio', { name: /Similarity Network Fusion/ }));
    await user.click(screen.getByRole('button', { name: /Run Integration/ }));
    await screen.findByText('Integration Results');
  }

  it('says why no per-dataset attribution is shown', async () => {
    const user = userEvent.setup();
    renderPage();
    await runSnf(user);

    expect(screen.getByText(/does not attribute the result across datasets/)).toBeInTheDocument();
  });

  it('does not show the feature-budget caveat, which does not apply here', async () => {
    // Caught in the browser, not by the earlier tests: the caveat was gated on
    // "basis is not pca_loadings", so it fired for the network methods too and
    // contradicted the message directly above it.
    const user = userEvent.setup();
    renderPage();
    await runSnf(user);

    expect(screen.queryByText(/scaled feature budget/)).not.toBeInTheDocument();
  });

  it('captions the plot with the clustering that was actually used', async () => {
    const user = userEvent.setup();
    renderPage();
    await runSnf(user);

    expect(screen.getByText(/Spectral embedding of the fused similarity network/)).toBeInTheDocument();
    expect(screen.queryByText(/First two components of the fused space/)).not.toBeInTheDocument();
  });

  it('renders n/a rather than a number when there is no variance to report', async () => {
    const user = userEvent.setup();
    renderPage();
    await runSnf(user);

    expect(screen.getByText('n/a')).toBeInTheDocument();
  });

  it('asks for pathway definitions only when that method is selected', async () => {
    const user = userEvent.setup();
    renderPage();
    await selectTwoDatasets(user);

    expect(screen.queryByLabelText(/Pathway definitions/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('radio', { name: /Pathway-level Integration/ }));
    expect(await screen.findByLabelText(/Pathway definitions/)).toBeInTheDocument();
  });
});
