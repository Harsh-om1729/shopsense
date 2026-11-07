import type { BrazilState, FreightRequest } from '../api/client'

export type LocationMode = 'zip' | 'coordinates'

export type FormState = {
  customer_state: BrazilState
  seller_state: BrazilState
  customer_zip: string
  seller_zip: string
  customer_lat: string
  customer_lng: string
  seller_lat: string
  seller_lng: string
  weight: string
  length: string
  height: string
  width: string
  price: string
  quantity: string
  category: string
}

export const INITIAL: FormState = {
  customer_state: 'SP',
  seller_state: 'RJ',
  customer_zip: '',
  seller_zip: '',
  customer_lat: '',
  customer_lng: '',
  seller_lat: '',
  seller_lng: '',
  weight: '',
  length: '',
  height: '',
  width: '',
  price: '',
  quantity: '1',
  category: '',
}

/** Turn a blank field into null, so the API knows it was left out. */
function optionalNumber(value: string) {
  return value.trim() === '' ? null : Number(value)
}

export function buildFreightRequest(form: FormState, mode: LocationMode): FreightRequest {
  const location =
    mode === 'zip'
      ? {
          customer_zip_prefix: optionalNumber(form.customer_zip),
          seller_zip_prefix: optionalNumber(form.seller_zip),
        }
      : {
          customer_lat: optionalNumber(form.customer_lat),
          customer_lng: optionalNumber(form.customer_lng),
          seller_lat: optionalNumber(form.seller_lat),
          seller_lng: optionalNumber(form.seller_lng),
        }
  return {
    customer_state: form.customer_state,
    seller_state: form.seller_state,
    ...location,
    product_weight_g: Number(form.weight),
    product_length_cm: Number(form.length),
    product_height_cm: Number(form.height),
    product_width_cm: Number(form.width),
    price: Number(form.price),
    quantity: Number(form.quantity),
    category: form.category.trim() || null,
  }
}
