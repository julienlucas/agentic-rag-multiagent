import { useState } from 'react';
import { Layout } from '@/components/Layout';
import { Dashboard } from '@/components/Dashboard';
import { Training } from '@/components/Training';
import { Models } from '@/components/Models';
import { Generate } from '@/components/Generate';

const Index = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedModelId, setSelectedModelId] = useState<string>();

  const handleSelectModel = (modelId: string) => {
    setSelectedModelId(modelId);
    setActiveTab('generate');
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard />;
      case 'training':
        return <Training />;
      case 'models':
        return <Models onSelectModel={handleSelectModel} />;
      case 'generate':
        return <Generate selectedModelId={selectedModelId} />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <Layout activeTab={activeTab} onTabChange={setActiveTab}>
      {renderContent()}
    </Layout>
  );
};

export default Index;
