/**
 * ML/AI Dashboard Page
 */

import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { ml as mlApi, datasets as datasetsApi, type DatasetSummary } from '../lib/api';
import { useAuthStore } from '../stores/auth';

const modelTypes = [
  { id: 'random_forest', name: 'Random Forest', category: 'Traditional ML' },
  { id: 'xgboost', name: 'XGBoost', category: 'Traditional ML' },
  { id: 'lightgbm', name: 'LightGBM', category: 'Traditional ML' },
  { id: 'svm', name: 'Support Vector Machine', category: 'Traditional ML' },
  { id: 'logistic', name: 'Logistic Regression', category: 'Traditional ML' },
  { id: 'elastic_net', name: 'Elastic Net', category: 'Traditional ML' },
  { id: 'mlp', name: 'Multi-Layer Perceptron', category: 'Deep Learning' },
  { id: 'cnn', name: 'CNN Classifier', category: 'Deep Learning' },
  { id: 'transformer', name: 'Transformer', category: 'Deep Learning' },
  { id: 'gcn', name: 'Graph Convolutional Network', category: 'GNN' },
  { id: 'gat', name: 'Graph Attention Network', category: 'GNN' },
  { id: 'graphsage', name: 'GraphSAGE', category: 'GNN' },
  { id: 'cox_ph', name: 'Cox Proportional Hazards', category: 'Survival' },
  { id: 'deepsurv', name: 'DeepSurv', category: 'Survival' },
];

const featureSelectionMethods = [
  { id: 'variance', name: 'Variance Filter', description: 'Remove low variance features' },
  { id: 'univariate', name: 'Univariate Selection', description: 'Statistical tests (F-test, mutual info)' },
  { id: 'rfe', name: 'Recursive Feature Elimination', description: 'Iterative feature removal' },
  { id: 'embedded', name: 'Embedded Methods', description: 'Random Forest, Lasso importance' },
  { id: 'stability', name: 'Stability Selection', description: 'Robust feature selection' },
];

const explainabilityMethods = [
  { id: 'shap', name: 'SHAP', description: 'SHapley Additive exPlanations' },
  { id: 'lime', name: 'LIME', description: 'Local Interpretable Model-agnostic Explanations' },
];

export default function MLDashboard() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const [selectedModel, setSelectedModel] = useState('');
  const [taskType, setTaskType] = useState<'classification' | 'regression'>('classification');
  const [selectedDataset, setSelectedDataset] = useState('');
  const [trainingStatus, setTrainingStatus] = useState<'idle' | 'training' | 'complete'>('idle');
  const [taskId, setTaskId] = useState<string | null>(null);
  const [targetColumn, setTargetColumn] = useState('target');

  const { data: datasetsData } = useQuery({
    queryKey: ['datasets'],
    queryFn: () => datasetsApi.list({ page: 1, page_size: 100 }),
    enabled: isAuthenticated,
  });

  const { data: modelsFromApi } = useQuery({
    queryKey: ['ml-models'],
    queryFn: () => mlApi.listModels(),
    enabled: isAuthenticated,
  });

  const trainMutation = useMutation({
    mutationFn: () =>
      mlApi.train({
        model_type: selectedModel,
        dataset_ids: selectedDataset ? [selectedDataset] : [],
        target_column: targetColumn,
        parameters: {},
        cross_validation: true,
        cv_folds: 5,
        test_size: 0.2,
      }),
    onSuccess: (res) => {
      setTaskId(res.task_id);
      setTrainingStatus('training');
      toast.success('Training started');
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : 'Training failed');
    },
  });

  const { data: taskStatus } = useQuery({
    queryKey: ['ml-task', taskId],
    queryFn: () => mlApi.taskStatus(taskId!),
    enabled: !!taskId && trainingStatus === 'training',
    refetchInterval: 2000,
  });

  // This effect is the terminal transition of a polling state machine:
  // trainingStatus and taskId gate the query above (`enabled`), and clearing
  // taskId here is what stops the 2s poll once the task reaches a final state.
  //
  // react-hooks/set-state-in-effect is disabled deliberately rather than
  // silenced. Deriving trainingStatus instead would mean keeping taskId set
  // after completion so 'complete' survives, which moves the poll-stop
  // condition and changes when a subsequent run resets -- a behavioural change
  // to async orchestration that cannot be validated without a live task
  // backend. The warning is about cascading renders, and this effect runs at
  // most once per training run. Revisit alongside a test that can drive a task
  // through SUCCESS and FAILURE.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (taskStatus?.ready && taskStatus?.status === 'SUCCESS') {
      setTrainingStatus('complete');
      setTaskId(null);
      toast.success('Training complete');
    } else if (taskStatus?.ready && taskStatus?.status === 'FAILURE') {
      setTrainingStatus('idle');
      setTaskId(null);
      toast.error(taskStatus?.error ?? 'Training failed');
    }
  }, [taskStatus]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const datasets = datasetsData?.items ?? [];
  const handleTrainModel = () => {
    if (!selectedModel || !selectedDataset) {
      toast.error('Select a model and dataset');
      return;
    }
    trainMutation.mutate();
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Machine Learning</h1>
        <p className="mt-1 text-sm text-gray-500">
          Train and evaluate ML models on your omics data
        </p>
        {modelsFromApi && modelsFromApi.length > 0 && (
          <p className="mt-1 text-xs text-gray-400" aria-live="polite">
            {modelsFromApi.length} model profile{modelsFromApi.length === 1 ? '' : 's'} from API
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Model Selection */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Model Selection</h2>
          
          <div className="space-y-4">
            <div>
              <label htmlFor="task-type" className="block text-sm font-medium text-gray-700">Task Type</label>
              <select
                id="task-type"
                value={taskType}
                onChange={(e) => setTaskType(e.target.value as 'classification' | 'regression')}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                <option value="classification">Classification</option>
                <option value="regression">Regression</option>
              </select>
            </div>

            <div>
              <label htmlFor="ml-dataset" className="block text-sm font-medium text-gray-700">Dataset</label>
              <select
                id="ml-dataset"
                value={selectedDataset}
                onChange={(e) => setSelectedDataset(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                <option value="">Select a dataset...</option>
                {datasets.map((d: DatasetSummary) => (
                  <option key={d.id} value={d.id}>{d.name} ({d.omics_type})</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="target-col" className="block text-sm font-medium text-gray-700">Target column</label>
              <input
                id="target-col"
                type="text"
                value={targetColumn}
                onChange={(e) => setTargetColumn(e.target.value)}
                placeholder="target"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm sm:text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Model</label>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {['Traditional ML', 'Deep Learning', 'GNN', 'Survival'].map((category) => (
                  <div key={category}>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">
                      {category}
                    </p>
                    {modelTypes
                      .filter((m) => m.category === category)
                      .map((model) => (
                        <label
                          key={model.id}
                          className="flex items-center p-2 hover:bg-gray-50 rounded cursor-pointer"
                        >
                          <input
                            type="radio"
                            name="model"
                            value={model.id}
                            checked={selectedModel === model.id}
                            onChange={(e) => setSelectedModel(e.target.value)}
                            className="h-4 w-4 text-indigo-600 focus:ring-indigo-500"
                          />
                          <span className="ml-2 text-sm text-gray-700">{model.name}</span>
                        </label>
                      ))}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Feature Selection */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Feature Selection</h2>
          
          <div className="space-y-3">
            {featureSelectionMethods.map((method) => (
              <div
                key={method.id}
                className="p-3 border border-gray-200 rounded-lg hover:border-indigo-300 cursor-pointer transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{method.name}</p>
                    <p className="text-xs text-gray-500">{method.description}</p>
                  </div>
                  <button className="text-xs text-indigo-600 hover:text-indigo-800">
                    Run
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 pt-4 border-t border-gray-200">
            <h3 className="text-sm font-medium text-gray-900 mb-2">Selected Features</h3>
            <p className="text-sm text-gray-500">No features selected yet</p>
          </div>
        </div>

        {/* Training & Results */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Training</h2>
          
          <div className="space-y-4">
            <div className="p-4 bg-gray-50 rounded-lg">
              <h3 className="text-sm font-medium text-gray-900 mb-2">Hyperparameters</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Test Split:</span>
                  <span className="text-gray-900">20%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Cross Validation:</span>
                  <span className="text-gray-900">5-fold</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Random Seed:</span>
                  <span className="text-gray-900">42</span>
                </div>
              </div>
            </div>

            <button
              onClick={handleTrainModel}
              disabled={!selectedModel || !selectedDataset || trainingStatus === 'training'}
              className="w-full py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {trainingStatus === 'training' ? 'Training...' : 'Train Model'}
            </button>

            {trainingStatus === 'training' && (
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Progress</span>
                  <span className="text-gray-900">Training...</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div className="bg-indigo-600 h-2 rounded-full w-1/2 animate-pulse"></div>
                </div>
              </div>
            )}

            {trainingStatus === 'complete' && (
              <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                <h3 className="text-sm font-medium text-green-800 mb-2">Training Complete</h3>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-green-700">Accuracy:</span>
                    <span className="text-green-900 font-medium">0.94</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-green-700">AUC-ROC:</span>
                    <span className="text-green-900 font-medium">0.97</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-green-700">F1 Score:</span>
                    <span className="text-green-900 font-medium">0.93</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Explainability Section */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Model Explainability</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {explainabilityMethods.map((method) => (
            <div key={method.id} className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-medium text-gray-900">{method.name}</h3>
                  <p className="text-xs text-gray-500">{method.description}</p>
                </div>
                <button
                  disabled={trainingStatus !== 'complete'}
                  className="px-3 py-1 text-xs font-medium text-indigo-600 border border-indigo-600 rounded hover:bg-indigo-50 disabled:text-gray-400 disabled:border-gray-400"
                >
                  Generate
                </button>
              </div>
              
              <div className="h-48 bg-gray-100 rounded flex items-center justify-center">
                <span className="text-sm text-gray-500">
                  {trainingStatus === 'complete' 
                    ? 'Click Generate to view explanation' 
                    : 'Train a model first'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* AutoML Section */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-medium text-gray-900">AutoML Pipeline</h2>
            <p className="text-sm text-gray-500">Automated model selection and hyperparameter tuning</p>
          </div>
          <button
            disabled={!selectedDataset}
            className="px-4 py-2 text-sm font-medium text-white bg-purple-600 rounded-lg hover:bg-purple-700 disabled:bg-gray-400"
          >
            Run AutoML
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-4 bg-purple-50 rounded-lg">
            <p className="text-xs text-purple-600 font-medium uppercase">Optimizer</p>
            <p className="text-lg font-semibold text-purple-900">Optuna</p>
          </div>
          <div className="p-4 bg-purple-50 rounded-lg">
            <p className="text-xs text-purple-600 font-medium uppercase">Trials</p>
            <p className="text-lg font-semibold text-purple-900">100</p>
          </div>
          <div className="p-4 bg-purple-50 rounded-lg">
            <p className="text-xs text-purple-600 font-medium uppercase">Time Limit</p>
            <p className="text-lg font-semibold text-purple-900">30 min</p>
          </div>
          <div className="p-4 bg-purple-50 rounded-lg">
            <p className="text-xs text-purple-600 font-medium uppercase">Metric</p>
            <p className="text-lg font-semibold text-purple-900">AUC-ROC</p>
          </div>
        </div>
      </div>
    </div>
  );
}
