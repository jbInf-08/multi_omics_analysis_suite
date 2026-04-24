/**
 * Multi-Omics Analysis Suite - React Frontend
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';

import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Projects from './pages/Projects';
import Datasets from './pages/Datasets';
import Analyses from './pages/Analyses';
import OmicsModule from './pages/OmicsModule';
import MLDashboard from './pages/MLDashboard';
import Integration from './pages/Integration';
import Settings from './pages/Settings';
import Tools from './pages/Tools';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/projects" element={<Projects />} />
            <Route path="/datasets" element={<Datasets />} />
            <Route path="/analyses" element={<Analyses />} />
            <Route path="/omics/:omicsType" element={<OmicsModule />} />
            <Route path="/ml" element={<MLDashboard />} />
            <Route path="/integration" element={<Integration />} />
            <Route path="/tools" element={<Tools />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Layout>
        <Toaster position="top-right" />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
