import type {
  ChannelAccountPluginArtifactRead,
  PluginConfigPreviewArtifactRead,
} from '../settingsTypes';

type PluginArtifact = PluginConfigPreviewArtifactRead | ChannelAccountPluginArtifactRead;

export function PluginArtifactList(props: {
  items: PluginArtifact[];
  artifactFallback: string;
  openLinkText: string;
  className?: string;
}) {
  if (props.items.length === 0) {
    return null;
  }

  return (
    <div className={`plugin-artifact-list ${props.className ?? ''}`.trim()}>
      {props.items.map((artifact, index) => {
        const key = ('key' in artifact && typeof artifact.key === 'string' && artifact.key)
          ? artifact.key
          : `${artifact.kind}-${index}`;
        if (artifact.kind === 'image_url' && artifact.url) {
          return (
            <div key={key} className="plugin-artifact-card">
              <div className="plugin-artifact-card__label">{artifact.label ?? props.artifactFallback}</div>
              <img
                className="plugin-artifact-card__image"
                src={artifact.url}
                alt={artifact.label ?? props.artifactFallback}
              />
            </div>
          );
        }
        if (artifact.kind === 'external_url' && artifact.url) {
          return (
            <div key={key} className="plugin-artifact-card">
              <div className="plugin-artifact-card__label">{artifact.label ?? props.artifactFallback}</div>
              <a className="plugin-artifact-card__link" href={artifact.url} target="_blank" rel="noreferrer">
                {artifact.label ?? props.openLinkText}
              </a>
            </div>
          );
        }
        if (artifact.kind === 'text' && artifact.text) {
          return (
            <div key={key} className="plugin-artifact-card">
              <div className="plugin-artifact-card__label">{artifact.label ?? props.artifactFallback}</div>
              <pre className="plugin-artifact-card__text">{artifact.text}</pre>
            </div>
          );
        }
        return null;
      })}
    </div>
  );
}
