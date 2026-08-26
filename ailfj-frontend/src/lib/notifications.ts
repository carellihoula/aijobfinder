export interface Notif {
  id: number
  type: "match" | "cortex" | "tip" | "analysis" | "alert"
  title: string
  body: string
  time: string
  read: boolean
}

export const MOCK_NOTIFS: Notif[] = [
  {
    id: 1,
    type: "match",
    title: "Nouveaux matchs disponibles",
    body: "Le Cortex vient d'être enrichi. 8 nouvelles offres correspondent à votre profil mis à jour.",
    time: "Il y a 1h",
    read: false,
  },
  {
    id: 2,
    type: "cortex",
    title: "Cortex mis à jour",
    body: "312 nouvelles offres ont été indexées cette nuit dans votre domaine.",
    time: "Il y a 8h",
    read: false,
  },
  {
    id: 3,
    type: "tip",
    title: "Conseil : renforcez votre profil",
    body: "Ajouter des compétences cloud (AWS, GCP) pourrait augmenter votre score moyen de +1.4 points.",
    time: "Hier",
    read: false,
  },
  {
    id: 4,
    type: "analysis",
    title: "Analyse terminée",
    body: "Votre dernière analyse a identifié 12 offres pertinentes avec un score moyen de 6.8/10.",
    time: "Il y a 2 jours",
    read: true,
  },
  {
    id: 5,
    type: "alert",
    title: "Offre expirante",
    body: "L'offre \"Développeur Full Stack\" chez TechCorp que vous avez sauvegardée expire dans 3 jours.",
    time: "Il y a 3 jours",
    read: true,
  },
]

import { scopedKey } from "./storageKey"

const notifsKey = () => scopedKey("notifs_read")

export function getReadIds(): Set<number> {
  try {
    return new Set(JSON.parse(localStorage.getItem(notifsKey()) || "[]"))
  } catch {
    return new Set()
  }
}

export function getUnreadCount(): number {
  const read = getReadIds()
  return MOCK_NOTIFS.filter((n) => !read.has(n.id)).length
}

export function markAllRead() {
  localStorage.setItem(notifsKey(), JSON.stringify(MOCK_NOTIFS.map((n) => n.id)))
}