"use client";

import { useApp } from "./AppContext";
import { useDialog } from "./useDialog";
import { Close } from "./Icons";

export function InstallButton() {
  const { t, install, showInstall } = useApp();
  return <button className="btn btn-ghost btn-sm" onClick={async () => {
    if (install.installed || !(await install.prompt())) showInstall();
  }}>{install.installed ? t("installed") : t("install_kettu")}</button>;
}

export function InstallSheet({ onClose }: { onClose: () => void }) {
  const { t, install } = useApp();
  const dialog = useDialog(onClose);
  return <>
    <div className="sheet-backdrop" onClick={onClose} />
    <div ref={dialog} className="sheet" role="dialog" aria-modal="true" aria-label={t("install_kettu")} tabIndex={-1}>
      <div className="sheet-inner">
        <div className="row"><h2 className="title">{t("install_kettu")}</h2><span className="spacer" />
          <button className="icon-btn" aria-label={t("done")} onClick={onClose}><Close /></button></div>
        <p>{t("install_explain")}</p>
        <p className="small">{t("install_phone_url")} <a href="https://kettu-gnani.vercel.app/">kettu-gnani.vercel.app</a></p>
        <div className="card stack"><strong>{install.platform === "ios" ? "iPhone / iPad" : install.platform === "android" ? "Android · Chrome" : "Chrome / Edge"}</strong>
          <p style={{ margin: 0 }}>{t(install.platform === "ios" ? "install_guide_ios" : install.platform === "android" ? "install_guide_android" : "install_guide_desktop")}</p>
        </div>
        <p className="small">{t("install_share_support")}</p>
        <p className="small">{t("install_offline_hint")}</p>
        <button className="btn btn-primary btn-block" onClick={onClose}>{t("done")}</button>
      </div>
    </div>
  </>;
}
