<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="loadError" class="error">{{ loadError }}</div>
    <div v-else>
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budgetLabel') }}</h3>
          <span class="budget-value">{{ formatCurrency(budget, currentCurrency) }}</span>
        </div>
        <input
          type="range"
          class="budget-slider"
          min="0"
          max="50000"
          step="100"
          v-model.number="budget"
        />
        <div v-if="recommendations" class="budget-summary">
          <span>
            {{ t('restocking.budgetUsed', {
              used: formatCurrency(recommendations.total_cost, currentCurrency),
              budget: formatCurrency(recommendations.budget, currentCurrency)
            }) }}
          </span>
          <span class="remaining">
            {{ t('restocking.remainingBudget') }}: {{ formatCurrency(recommendations.remaining_budget, currentCurrency) }}
          </span>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.title') }} ({{ recommendations ? recommendations.items.length : 0 }})</h3>
          <button
            class="place-order-btn"
            :disabled="!recommendations || recommendations.items.length === 0 || placingOrder"
            @click="placeOrder"
          >
            {{ placingOrder ? t('restocking.placingOrder') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="successMessage" class="success-message">{{ successMessage }}</div>
        <div v-if="orderError" class="error">{{ orderError }}</div>

        <div v-if="!recommendations || recommendations.items.length === 0" class="empty-state">
          {{ t('restocking.noRecommendations') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.category') }}</th>
                <th>{{ t('restocking.table.warehouse') }}</th>
                <th>{{ t('restocking.table.quantityOnHand') }}</th>
                <th>{{ t('restocking.table.reorderPoint') }}</th>
                <th>{{ t('restocking.table.forecastedDemand') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th>{{ t('restocking.table.recommendedQuantity') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.lineTotal') }}</th>
                <th>{{ t('restocking.table.reason') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in recommendations.items" :key="item.sku">
                <td><strong>{{ item.sku }}</strong></td>
                <td>{{ item.item_name }}</td>
                <td>{{ item.category }}</td>
                <td>{{ item.warehouse }}</td>
                <td>{{ item.quantity_on_hand }}</td>
                <td>{{ item.reorder_point }}</td>
                <td>{{ item.forecasted_demand }}</td>
                <td>
                  <span :class="['badge', item.trend]">
                    {{ t(`trends.${item.trend}`) }}
                  </span>
                </td>
                <td><strong>{{ item.recommended_quantity }}</strong></td>
                <td>{{ formatCurrency(item.unit_cost, currentCurrency) }}</td>
                <td><strong>{{ formatCurrency(item.line_total, currentCurrency) }}</strong></td>
                <td class="reason-cell">{{ t(`restocking.reasons.${urgencyReasonKey(item.urgency_reason)}`) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency } from '../utils/currency'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency } = useI18n()

    const budget = ref(5000)
    const loading = ref(true)
    const loadError = ref(null)
    const recommendations = ref(null)

    const placingOrder = ref(false)
    const successMessage = ref(null)
    const orderError = ref(null)

    let debounceTimer = null

    // Maps raw backend urgency_reason strings to restocking.reasons.* translation keys
    const URGENCY_REASON_KEYS = {
      'Below reorder point, demand increasing': 'belowReorderAndGrowing',
      'Below reorder point': 'belowReorder',
      'Demand increasing': 'demandGrowing',
      'Restock recommended': 'restockRecommended'
    }

    const urgencyReasonKey = (reason) => URGENCY_REASON_KEYS[reason] || 'restockRecommended'

    const loadRecommendations = async () => {
      try {
        loadError.value = null
        recommendations.value = await api.getRestockingRecommendations(budget.value)
      } catch (err) {
        loadError.value = 'Failed to load restocking recommendations: ' + err.message
      } finally {
        loading.value = false
      }
    }

    watch(budget, () => {
      if (debounceTimer) clearTimeout(debounceTimer)
      debounceTimer = setTimeout(() => {
        loadRecommendations()
      }, 400)
    })

    const placeOrder = async () => {
      successMessage.value = null
      orderError.value = null
      placingOrder.value = true
      try {
        const order = await api.createRestockingOrder(budget.value)
        successMessage.value = t('restocking.orderSuccess', { orderNumber: order.order_number })
      } catch (err) {
        orderError.value = 'Failed to place order: ' + err.message
      } finally {
        placingOrder.value = false
      }
    }

    onMounted(() => loadRecommendations())

    return {
      t,
      currentCurrency,
      formatCurrency,
      budget,
      loading,
      loadError,
      recommendations,
      placingOrder,
      successMessage,
      orderError,
      placeOrder,
      urgencyReasonKey
    }
  }
}
</script>

<style scoped>
.budget-slider {
  width: 100%;
  accent-color: #2563eb;
  margin: 0.5rem 0 1rem;
}

.budget-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
}

.budget-summary {
  display: flex;
  justify-content: space-between;
  font-size: 0.875rem;
  color: #64748b;
  margin-top: 0.5rem;
}

.budget-summary .remaining {
  font-weight: 600;
  color: #0f172a;
}

.place-order-btn {
  background: #2563eb;
  color: white;
  border: none;
  padding: 0.5rem 1.25rem;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.875rem;
  cursor: pointer;
  transition: background 0.2s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.success-message {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #065f46;
  padding: 0.875rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.938rem;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #64748b;
  font-size: 0.938rem;
}

.reason-cell {
  max-width: 260px;
}
</style>
