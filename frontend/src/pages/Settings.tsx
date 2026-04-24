/**
 * Settings Page
 */

import { useState } from 'react';

export default function Settings() {
  const [activeTab, setActiveTab] = useState('general');

  const tabs = [
    { id: 'general', name: 'General' },
    { id: 'account', name: 'Account' },
    { id: 'analysis', name: 'Analysis Defaults' },
    { id: 'notifications', name: 'Notifications' },
    { id: 'api', name: 'API Keys' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-sm text-gray-500">
          Manage your preferences and account settings
        </p>
      </div>

      <div className="bg-white shadow rounded-lg">
        {/* Tab Navigation */}
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8 px-6" aria-label="Tabs">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.id
                    ? 'border-indigo-500 text-indigo-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab.name}
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {activeTab === 'general' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">General Settings</h3>
                
                <div className="space-y-4">
                  <div>
                    <label htmlFor="theme-select" className="block text-sm font-medium text-gray-700">Theme</label>
                    <select id="theme-select" className="mt-1 block w-full max-w-xs rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
                      <option>Light</option>
                      <option>Dark</option>
                      <option>System</option>
                    </select>
                  </div>

                  <div>
                    <label htmlFor="language-select" className="block text-sm font-medium text-gray-700">Language</label>
                    <select id="language-select" className="mt-1 block w-full max-w-xs rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
                      <option>English</option>
                      <option>Spanish</option>
                      <option>French</option>
                      <option>German</option>
                    </select>
                  </div>

                  <div>
                    <label htmlFor="timezone-select" className="block text-sm font-medium text-gray-700">Timezone</label>
                    <select id="timezone-select" className="mt-1 block w-full max-w-xs rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
                      <option>UTC</option>
                      <option>America/New_York</option>
                      <option>America/Los_Angeles</option>
                      <option>Europe/London</option>
                      <option>Asia/Tokyo</option>
                    </select>
                  </div>

                  <div className="flex items-center justify-between py-4 border-t border-gray-200">
                    <div>
                      <p id="autosave-label" className="text-sm font-medium text-gray-900">Auto-save projects</p>
                      <p className="text-sm text-gray-500">Automatically save changes to projects</p>
                    </div>
                    <button
                      type="button"
                      role="switch"
                      aria-checked="true"
                      aria-labelledby="autosave-label"
                      className="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent bg-indigo-600 transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                    >
                      <span className="translate-x-5 pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"></span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'account' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">Account Information</h3>
                
                <div className="space-y-4">
                  <div>
                    <label htmlFor="account-email" className="block text-sm font-medium text-gray-700">Email</label>
                    <input
                      id="account-email"
                      type="email"
                      defaultValue="user@example.com"
                      className="mt-1 block w-full max-w-md rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                    />
                  </div>

                  <div>
                    <label htmlFor="account-username" className="block text-sm font-medium text-gray-700">Username</label>
                    <input
                      id="account-username"
                      type="text"
                      defaultValue="researcher"
                      className="mt-1 block w-full max-w-md rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                    />
                  </div>

                  <div>
                    <label htmlFor="account-fullname" className="block text-sm font-medium text-gray-700">Full Name</label>
                    <input
                      id="account-fullname"
                      type="text"
                      defaultValue="Jane Researcher"
                      className="mt-1 block w-full max-w-md rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                    />
                  </div>

                  <div>
                    <label htmlFor="account-org" className="block text-sm font-medium text-gray-700">Organization</label>
                    <input
                      id="account-org"
                      type="text"
                      defaultValue="Research Institute"
                      className="mt-1 block w-full max-w-md rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                    />
                  </div>
                </div>
              </div>

              <div className="pt-6 border-t border-gray-200">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Change Password</h3>
                
                <div className="space-y-4 max-w-md">
                  <div>
                    <label htmlFor="current-password" className="block text-sm font-medium text-gray-700">Current Password</label>
                    <input
                      id="current-password"
                      type="password"
                      autoComplete="current-password"
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                    />
                  </div>
                  <div>
                    <label htmlFor="new-password" className="block text-sm font-medium text-gray-700">New Password</label>
                    <input
                      id="new-password"
                      type="password"
                      autoComplete="new-password"
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                    />
                  </div>
                  <div>
                    <label htmlFor="confirm-password" className="block text-sm font-medium text-gray-700">Confirm New Password</label>
                    <input
                      id="confirm-password"
                      type="password"
                      autoComplete="new-password"
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                    />
                  </div>
                  <button className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700">
                    Update Password
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'analysis' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">Analysis Defaults</h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <h4 className="text-sm font-medium text-gray-700">Statistical Settings</h4>
                    
                    <div>
                      <label htmlFor="alpha-level" className="block text-sm text-gray-600">Significance Level (alpha)</label>
                      <input
                        id="alpha-level"
                        type="number"
                        defaultValue={0.05}
                        step={0.01}
                        min={0.001}
                        max={0.1}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                      />
                    </div>

                    <div>
                      <label htmlFor="multiple-testing" className="block text-sm text-gray-600">Multiple Testing Correction</label>
                      <select id="multiple-testing" className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
                        <option>Benjamini-Hochberg (FDR)</option>
                        <option>Bonferroni</option>
                        <option>Holm</option>
                        <option>None</option>
                      </select>
                    </div>

                    <div>
                      <label htmlFor="default-norm" className="block text-sm text-gray-600">Default Normalization</label>
                      <select id="default-norm" className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
                        <option>Quantile</option>
                        <option>Z-score</option>
                        <option>Log2</option>
                        <option>TPM</option>
                      </select>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <h4 className="text-sm font-medium text-gray-700">ML Settings</h4>
                    
                    <div>
                      <label htmlFor="test-set-size" className="block text-sm text-gray-600">Test Set Size</label>
                      <select id="test-set-size" className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
                        <option>20%</option>
                        <option>25%</option>
                        <option>30%</option>
                      </select>
                    </div>

                    <div>
                      <label htmlFor="cv-folds" className="block text-sm text-gray-600">Cross-Validation Folds</label>
                      <select id="cv-folds" className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
                        <option>5</option>
                        <option>10</option>
                        <option>Leave-One-Out</option>
                      </select>
                    </div>

                    <div>
                      <label htmlFor="random-seed" className="block text-sm text-gray-600">Random Seed</label>
                      <input
                        id="random-seed"
                        type="number"
                        defaultValue={42}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'notifications' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">Notification Preferences</h3>
                
                <div className="space-y-4">
                  {[
                    { id: 'analysis_complete', label: 'Analysis Complete', description: 'Notify when an analysis finishes' },
                    { id: 'analysis_failed', label: 'Analysis Failed', description: 'Notify when an analysis encounters an error' },
                    { id: 'data_uploaded', label: 'Data Upload Complete', description: 'Notify when data upload finishes' },
                    { id: 'ml_training', label: 'ML Training Complete', description: 'Notify when model training finishes' },
                    { id: 'collaboration', label: 'Collaboration Updates', description: 'Notify when collaborators make changes' },
                    { id: 'system_updates', label: 'System Updates', description: 'Notify about platform updates and maintenance' },
                  ].map((item) => (
                    <div key={item.id} className="flex items-center justify-between py-4 border-b border-gray-200">
                      <div>
                        <p className="text-sm font-medium text-gray-900">{item.label}</p>
                        <p className="text-sm text-gray-500">{item.description}</p>
                      </div>
                      <div className="flex space-x-4">
                        <label className="flex items-center cursor-pointer">
                          <input type="checkbox" defaultChecked className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 rounded" aria-label={`${item.label} email notifications`} />
                          <span className="ml-2 text-sm text-gray-600">Email</span>
                        </label>
                        <label className="flex items-center cursor-pointer">
                          <input type="checkbox" defaultChecked className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 rounded" aria-label={`${item.label} in-app notifications`} />
                          <span className="ml-2 text-sm text-gray-600">In-app</span>
                        </label>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'api' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">API Keys</h3>
                
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
                  <div className="flex">
                    <svg className="h-5 w-5 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                    <div className="ml-3">
                      <p className="text-sm text-yellow-700">
                        Keep your API keys secure. Do not share them publicly or commit them to version control.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-900">Production API Key</p>
                        <p className="text-sm text-gray-500 font-mono mt-1">moas_prod_****************************1234</p>
                      </div>
                      <div className="flex space-x-2">
                        <button className="px-3 py-1 text-sm text-gray-600 border border-gray-300 rounded hover:bg-gray-50">
                          Copy
                        </button>
                        <button className="px-3 py-1 text-sm text-red-600 border border-red-300 rounded hover:bg-red-50">
                          Revoke
                        </button>
                      </div>
                    </div>
                    <p className="text-xs text-gray-400 mt-2">Created: Jan 15, 2026</p>
                  </div>

                  <div className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-900">Development API Key</p>
                        <p className="text-sm text-gray-500 font-mono mt-1">moas_dev_****************************5678</p>
                      </div>
                      <div className="flex space-x-2">
                        <button className="px-3 py-1 text-sm text-gray-600 border border-gray-300 rounded hover:bg-gray-50">
                          Copy
                        </button>
                        <button className="px-3 py-1 text-sm text-red-600 border border-red-300 rounded hover:bg-red-50">
                          Revoke
                        </button>
                      </div>
                    </div>
                    <p className="text-xs text-gray-400 mt-2">Created: Jan 20, 2026</p>
                  </div>

                  <button className="flex items-center px-4 py-2 text-sm font-medium text-indigo-600 border border-indigo-600 rounded-md hover:bg-indigo-50">
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Generate New API Key
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Save Button */}
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex justify-end rounded-b-lg">
          <button className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}
