import { useEffect, useState } from "react";
import { api, Template } from "../api/client";

export default function Templates() {
  const [templates, setTemplates] = useState<Template[]>([]);
  useEffect(() => { api.listTemplates().then(setTemplates); }, []);
  return (
    <div>
      <h1>Templates</h1>
      <ul>
        {templates.map((t) => (
          <li key={t.id}><strong>{t.name}</strong>: {t.prompt}</li>
        ))}
      </ul>
    </div>
  );
}
