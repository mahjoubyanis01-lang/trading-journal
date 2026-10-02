import { useEffect, useState } from 'react';
import { ChevronDown, Loader2, Save } from 'lucide-react';
import { api } from '../services/api';
import { useAsync } from '../hooks/useAsync';
import { useToast } from '../components/ui/Toast';
import { PageHeader } from '../components/ui/Kpi';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { ErrorState, Loading } from '../components/ui/States';
import type { AppConfig } from '../types';

export function SettingsPage() {
  const settings = useAsync(() => api.getSettings(), []);
  const config = useAsync<AppConfig>(() => api.getConfig(), []);
  const toast = useToast();

  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  useEffect(() => {
    if (settings.data) setDraft(settings.data.settings);
  }, [settings.data]);

  if ((settings.loading && !settings.data) || (config.loading && !config.data)) return <Loading />;
  if (settings.error && !settings.data) return <ErrorState message={settings.error} onRetry={settings.refetch} />;

  const keys = Object.keys(draft);
  const dirty = settings.data
    ? keys.some((k) => draft[k] !== settings.data!.settings[k])
    : false;

  async function save() {
    setSaving(true);
    try {
      await api.putSettings(draft);
      toast('success', 'Settings saved');
      settings.refetch();
    } catch (e) {
      toast('error', e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  const c = config.data;

  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="System configuration"
        actions={
          <Button variant="primary" size="sm" onClick={save} disabled={!dirty || saving}>
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            Save changes
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Runtime config (read-only) */}
        <Card>
          <CardHeader title="Runtime" subtitle="Read-only system status" />
          <CardBody className="space-y-0">
            {c && (
              <>
                <ConfigRow label="Mock mode" value={c.mock_mode ? 'ON' : 'OFF'} tone={c.mock_mode ? 'info' : 'ok'} />
                <ConfigRow label="Credential backend" value={c.credential_backend} />
                <ConfigRow label="Confidence · auto-map" value={`${(c.confidence_auto * 100).toFixed(0)}%`} />
                <ConfigRow label="Confidence · confirm" value={`${(c.confidence_confirm * 100).toFixed(0)}%`} />
                <ConfigRow label="Heartbeat timeout" value={`${c.heartbeat_timeout_s}s`} />
              </>
            )}
          </CardBody>
        </Card>

        {/* Editable settings */}
        <Card>
          <CardHeader title="Preferences" subtitle="Simple, editable settings" />
          <CardBody className="space-y-3">
            {keys.length === 0 ? (
              <p className="py-4 text-center text-xs text-zinc-600">No editable settings.</p>
            ) : (
              keys.map((k) => (
                <label key={k} className="block">
                  <span className="mb-1 block text-xs font-medium text-zinc-400">{k}</span>
                  <Input
                    value={draft[k] ?? ''}
                    onChange={(e) => setDraft((d) => ({ ...d, [k]: e.target.value }))}
                  />
                </label>
              ))
            )}
          </CardBody>
        </Card>
      </div>

      {/* Advanced, tucked away */}
      <div className="mt-4">
        <button
          onClick={() => setAdvancedOpen((o) => !o)}
          className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300"
        >
          <ChevronDown size={14} className={advancedOpen ? 'rotate-180 transition-transform' : 'transition-transform'} />
          Advanced
        </button>
        {advancedOpen && (
          <Card className="mt-2">
            <CardBody>
              <pre className="overflow-x-auto text-2xs text-zinc-500">
                {JSON.stringify({ settings: settings.data?.settings, config: c }, null, 2)}
              </pre>
            </CardBody>
          </Card>
        )}
      </div>
    </>
  );
}

function ConfigRow({ label, value, tone }: { label: string; value: string; tone?: 'ok' | 'info' }) {
  return (
    <div className="flex items-center justify-between border-b border-edge/50 py-2 text-sm last:border-0">
      <span className="text-zinc-500">{label}</span>
      <span
        className={`font-medium ${tone === 'ok' ? 'text-op' : tone === 'info' ? 'text-info' : 'text-zinc-200'}`}
      >
        {value}
      </span>
    </div>
  );
}
