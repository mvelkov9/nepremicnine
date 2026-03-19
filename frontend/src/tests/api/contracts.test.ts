/**
 * API contract tests — validate that our TypeScript types
 * match expected API response shapes.
 */
import { describe, it, expect } from 'vitest'
import type {
  User,
  Dataset,
  TrainingJob,
  ModelInfo,
  PredictionResult,
  HealthStatus,
  RegionLookup,
} from '../../types/api'

describe('API response contracts', () => {
  describe('User type', () => {
    it('has all required fields with correct types', () => {
      const user: User = {
        id: 1,
        email: 'test@test.com',
        full_name: 'Test User',
        avatar_url: null,
        role: 'viewer',
        is_active: true,
        created_at: '2024-01-01T00:00:00Z',
      }
      expect(user.id).toBeTypeOf('number')
      expect(user.email).toBeTypeOf('string')
      expect(user.role).toMatch(/^(admin|viewer)$/)
      expect(user.is_active).toBeTypeOf('boolean')
      expect(user.created_at).toBeTypeOf('string')
    })

    it('allows null for optional fields', () => {
      const user: User = {
        id: 1,
        email: 'a@b.com',
        full_name: null,
        avatar_url: null,
        role: 'admin',
        is_active: true,
        created_at: '2024-01-01T00:00:00Z',
      }
      expect(user.full_name).toBeNull()
      expect(user.avatar_url).toBeNull()
    })
  })

  describe('TrainingJob type', () => {
    it('has valid status enum', () => {
      const validStatuses: TrainingJob['status'][] = ['queued', 'running', 'completed', 'failed']
      validStatuses.forEach((s) => expect(s).toBeTruthy())
    })

    it('accepts a complete job object', () => {
      const job: TrainingJob = {
        job_id: 'abc123',
        status: 'running',
        stage: 'fitting',
        progress: 45,
        current_model: 'HistGradientBoosting',
        current_model_index: 1,
        total_models: 3,
        elapsed_sec: 120.5,
        eta_sec: 145.0,
        error: null,
      }
      expect(job.progress).toBeGreaterThanOrEqual(0)
      expect(job.progress).toBeLessThanOrEqual(100)
    })
  })

  describe('Dataset type', () => {
    it('has all required fields', () => {
      const ds: Dataset = {
        id: 1,
        original_name: 'train.csv',
        stored_path: '/data/uploads/abc.csv',
        source_type: 'csv',
        row_count: 5000,
        columns_json: ['price', 'area', 'municipality'],
        file_hash: 'abcdef1234567890',
        uploaded_by: 1,
        uploaded_at: '2024-01-01T00:00:00Z',
      }
      expect(ds.file_hash).toBeTypeOf('string')
      expect(ds.row_count).toBeTypeOf('number')
    })
  })

  describe('ModelInfo type', () => {
    it('has metrics and metadata', () => {
      const info: ModelInfo = {
        version: '2024-01-01_120000',
        trained_at: '2024-01-01T12:00:00Z',
        algorithm: 'HistGradientBoostingRegressor',
        r2: 0.89,
        mae: 15000,
        rmse: 22000,
        row_count: 10000,
        property_types: ['Stanovanje', 'Hiša'],
      }
      expect(info.r2).toBeGreaterThanOrEqual(0)
      expect(info.r2).toBeLessThanOrEqual(1)
      expect(info.property_types).toBeInstanceOf(Array)
    })
  })

  describe('PredictionResult type', () => {
    it('has predicted price', () => {
      const result: PredictionResult = {
        predicted_price_eur: 185000,
        used_features: { area: 75, property_type: 'Stanovanje' },
      }
      expect(result.predicted_price_eur).toBeTypeOf('number')
      expect(result.predicted_price_eur).toBeGreaterThan(0)
    })
  })

  describe('HealthStatus type', () => {
    it('has valid status values', () => {
      const health: HealthStatus = {
        status: 'ok',
        version: '0.11.0',
        database: 'connected',
        redis: 'connected',
        model: 'loaded',
      }
      expect(['ok', 'degraded', 'error']).toContain(health.status)
    })
  })

  describe('RegionLookup type', () => {
    it('has municipality and region names', () => {
      const region: RegionLookup = {
        obcina_sifra: 61,
        obcina_naziv: 'Ljubljana',
        regija_naziv: 'Osrednjeslovenska',
      }
      expect(region.obcina_naziv).toBeTypeOf('string')
      expect(region.regija_naziv).toBeTypeOf('string')
    })
  })
})
