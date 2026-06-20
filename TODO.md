# TODO - Multi-product Sales Entry

- [x] Update Sales Entry UI (templates/sales.html)
  - [ ] Add “Add Item” button
  - [ ] Add cart table (Product, Quantity, Unit Price, Item Total, Remove)
  - [ ] Add totals section (Total Items, Grand Total ₹)
  - [ ] Add “Complete Sale / Generate Bill” submit button
  - [ ] Add hidden fields for cart submission (payment_type, cart_json, grand_total)


- [ ] Implement cart behavior (static/app.js)
  - [ ] Maintain cart items in JS state
  - [ ] Handle “Add Item” (merge quantities for same product)
  - [ ] Render/remove cart rows
  - [ ] Update totals
  - [ ] Prepare hidden inputs (cart_json, payment_type, grand_total)
  - [ ] Keep existing live unit/total price calculation for current item form

- [ ] Update backend workflow (app.py)
  - [ ] Modify /sales POST to accept cart_json
  - [ ] Validate payment_type and cart items
  - [ ] DB transaction: lock products (FOR UPDATE)
  - [ ] Validate stock availability per cart item
  - [ ] Insert one sales row per cart item
  - [ ] Reduce product stock for all cart items
  - [ ] Commit transaction and redirect

- [ ] Basic verification
  - [ ] Manual test: add multiple products and complete sale
  - [ ] Verify dashboard totals and reports aggregation remain correct
  - [ ] Verify reports/history table structure unchanged

