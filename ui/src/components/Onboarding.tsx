import { useState } from "react";
import { Link } from "react-router-dom";
import { api, Health } from "../api/client";

interface OnboardingProps {
  health: Health | null;
  onRefresh: () => void;
}

function useDownload(action: () => Promise<unknown>) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function trigger(onRefresh: () => void) {
    setDownloading(true);
    setError(null);
    try {
      await action();
      onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDownloading(false);
    }
  }

  return { downloading, error, trigger };
}

export default function Onboarding({ health, onRefresh }: OnboardingProps) {
  const [dismissed, setDismissed] = useState(false);

  const diarization = useDownload(() => api.downloadDiarizationModels());
  const cuda = useDownload(() => api.downloadCudaLibraries());

  if (dismissed || health === null) return null;

  const issues: React.ReactNode[] = [];

  if (health.webview2 === false) {
    issues.push(
      <div key="webview2" className="onboarding-card panel">
        <strong>WebView2 runtime missing</strong>
        <p>
          pywebview requires the Microsoft WebView2 runtime to display the app
          window.{" "}
          <a
            href="https://developer.microsoft.com/microsoft-edge/webview2/"
            target="_blank"
            rel="noreferrer"
          >
            Download the Evergreen installer
          </a>
          , then restart Muesli.
        </p>
      </div>
    );
  }

  if (health.ollama === false) {
    issues.push(
      <div key="ollama" className="onboarding-card panel">
        <strong>Ollama not reachable</strong>
        <p>
          Muesli uses Ollama to enhance meeting notes locally.{" "}
          <a
            href="https://ollama.com/download"
            target="_blank"
            rel="noreferrer"
          >
            Install Ollama
          </a>
          , then run <code>ollama pull</code> with your preferred model. Or{" "}
          <Link to="/settings">use a cloud model instead</Link>.
        </p>
      </div>
    );
  }

  if (health.diarization_models === false) {
    issues.push(
      <div key="diarization" className="onboarding-card panel">
        <strong>Speaker models not downloaded</strong>
        <p>
          Speaker separation requires a one-time download of ~32 MB of ONNX
          model files.
        </p>
        {diarization.error && (
          <p className="onboarding-error">{diarization.error}</p>
        )}
        <button
          className="button-primary"
          disabled={diarization.downloading}
          onClick={() => diarization.trigger(onRefresh)}
        >
          {diarization.downloading ? "Downloading…" : "Download now"}
        </button>
      </div>
    );
  }

  if (health.gpu_present === true && health.cuda_libraries === false) {
    issues.push(
      <div key="cuda" className="onboarding-card panel">
        <strong>Enable GPU acceleration (optional)</strong>
        <p>
          An NVIDIA GPU was detected. Downloading the NVIDIA CUDA libraries
          (~1 GB, one time) will make transcription significantly faster. This
          is entirely optional — Muesli works fine on CPU.
        </p>
        {cuda.error && (
          <p className="onboarding-error">{cuda.error}</p>
        )}
        <button
          className="button-primary"
          disabled={cuda.downloading}
          onClick={() => cuda.trigger(onRefresh)}
        >
          {cuda.downloading ? "Downloading…" : "Download CUDA libraries"}
        </button>
      </div>
    );
  }

  if (issues.length === 0) return null;

  return (
    <div className="onboarding">
      <div className="onboarding-header">
        <span className="onboarding-title">Setup needed</span>
        <button
          className="onboarding-dismiss"
          aria-label="Dismiss setup notices"
          onClick={() => setDismissed(true)}
        >
          ×
        </button>
      </div>
      {issues}
    </div>
  );
}
