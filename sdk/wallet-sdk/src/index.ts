export { WalletApiClient, WalletApiError } from "./client"
export type { WalletBalance, WalletHistoryEvent, PermittedCategories, RedeemResult } from "./client"
export { WalletBalanceCard } from "./components/WalletBalanceCard"
export { TransactionHistory } from "./components/TransactionHistory"
export { QuickPay } from "./components/QuickPay"
export { OfflineQueueStatus } from "./components/OfflineQueueStatus"
export { OfflineWalletQueue } from "./offlineQueue"
export type { QueuedPayment } from "./offlineQueue"

// Host apps import the theme contract stylesheet directly:
//   import "@finverge/sovereignx-wallet-sdk/src/theme.css"
// then override the --sx-wallet-* custom properties — see README.md.
