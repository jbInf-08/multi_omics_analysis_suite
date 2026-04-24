/**
 * Main Layout Component
 */

import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import clsx from 'clsx';

interface LayoutProps {
  children: React.ReactNode;
}

const omicsCategories = [
  {
    name: 'Core Omics',
    items: [
      { name: 'Genomics', path: '/omics/genomics' },
      { name: 'Transcriptomics', path: '/omics/transcriptomics' },
      { name: 'Proteomics', path: '/omics/proteomics' },
      { name: 'Metabolomics', path: '/omics/metabolomics' },
      { name: 'Epigenomics', path: '/omics/epigenomics' },
      { name: 'Metagenomics', path: '/omics/metagenomics' },
      { name: 'Pharmacogenomics', path: '/omics/pharmacogenomics' },
      { name: 'Lipidomics', path: '/omics/lipidomics' },
    ],
  },
  {
    name: 'Modification Omics',
    items: [
      { name: 'Phosphoproteomics', path: '/omics/phosphoproteomics' },
      { name: 'Glycomics', path: '/omics/glycomics' },
      { name: 'Acetylomics', path: '/omics/acetylomics' },
      { name: 'Methylomics', path: '/omics/methylomics' },
      { name: 'Ubiquitomics', path: '/omics/ubiquitomics' },
      { name: 'Kinomics', path: '/omics/kinomics' },
    ],
  },
  {
    name: 'Interaction Omics',
    items: [
      { name: 'Interactomics', path: '/omics/interactomics' },
      { name: 'Connectomics', path: '/omics/connectomics' },
      { name: 'Regulomics', path: '/omics/regulomics' },
    ],
  },
  {
    name: 'Clinical Omics',
    items: [
      { name: 'Immunogenomics', path: '/omics/immunogenomics' },
      { name: 'Toxicogenomics', path: '/omics/toxicogenomics' },
      { name: 'Nutrigenomics', path: '/omics/nutrigenomics' },
    ],
  },
];

const mainNavItems = [
  { name: 'Dashboard', path: '/', icon: 'chart-bar' },
  { name: 'Projects', path: '/projects', icon: 'folder' },
  { name: 'Datasets', path: '/datasets', icon: 'database' },
  { name: 'Analyses', path: '/analyses', icon: 'beaker' },
  { name: 'Integration', path: '/integration', icon: 'link' },
  { name: 'Tools', path: '/tools', icon: 'beaker' },
  { name: 'ML/AI', path: '/ml', icon: 'cpu-chip' },
];

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 rounded-md hover:bg-gray-100"
              aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <Link to="/" className="flex items-center space-x-2">
              <svg className="w-8 h-8 text-indigo-600" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
              </svg>
              <span className="text-xl font-bold text-gray-900">Multi-Omics Suite</span>
            </Link>
          </div>
          
          <div className="flex items-center space-x-4">
            <button className="p-2 rounded-full hover:bg-gray-100" aria-label="Notifications">
              <svg className="w-6 h-6 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
            </button>
            <Link to="/settings" className="p-2 rounded-full hover:bg-gray-100">
              <svg className="w-6 h-6 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </Link>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside className={clsx(
          'bg-white border-r border-gray-200 transition-all duration-300 overflow-y-auto',
          sidebarOpen ? 'w-64' : 'w-0'
        )}>
          <nav className="p-4 space-y-6">
            {/* Main Navigation */}
            <div>
              <h3 className="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Main
              </h3>
              <div className="mt-2 space-y-1">
                {mainNavItems.map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={clsx(
                      'flex items-center px-3 py-2 text-sm font-medium rounded-md',
                      location.pathname === item.path
                        ? 'bg-indigo-50 text-indigo-600'
                        : 'text-gray-700 hover:bg-gray-50'
                    )}
                  >
                    {item.name}
                  </Link>
                ))}
              </div>
            </div>

            {/* Omics Categories */}
            {omicsCategories.map((category) => (
              <div key={category.name}>
                <h3 className="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  {category.name}
                </h3>
                <div className="mt-2 space-y-1">
                  {category.items.map((item) => (
                    <Link
                      key={item.path}
                      to={item.path}
                      className={clsx(
                        'flex items-center px-3 py-2 text-sm font-medium rounded-md',
                        location.pathname === item.path
                          ? 'bg-indigo-50 text-indigo-600'
                          : 'text-gray-700 hover:bg-gray-50'
                      )}
                    >
                      {item.name}
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </nav>
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-6 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
