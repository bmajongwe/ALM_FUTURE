from django.db import transaction
from decimal import Decimal
from ALM_APP.models import (
    HQLAStock, 
    HQLAStockInflow,
    HQLAStockOutflow,
    LCRCalculation
)

def calculate_and_store_lcr(fic_mis_date):
    """
    Calculates and stores LCR-related records based on:
      - HQLAStock totals (overall_after, level2a_after, level2b_after)
      - HQLAStockInflow totals (overall and distinct level totals)
      - HQLAStockOutflow totals (overall and distinct level totals)
      
    Additionally, calculates Net Cash Outflows and LCR Ratio using overall totals.
    The field total_type is populated to indicate whether a record is an overall total or a level total.
    
    In this updated version the level totals are inserted first for each category (HQLA, inflows, outflows)
    and the overall totals appear at the bottom of their respective category block.
    """
    try:
        print(f"🔍 Starting LCR Calculation for {fic_mis_date}")

        # 1️⃣ Delete old LCRCalculation records for this date
        deleted_count = LCRCalculation.objects.filter(fic_mis_date=fic_mis_date).delete()
        print(f"🗑️ Deleted {deleted_count[0]} old LCR records for {fic_mis_date}")

        # =============================
        # Process HQLAStock totals
        # =============================
        overall_hqla_qs = HQLAStock.objects.filter(
            fic_mis_date=fic_mis_date, 
            is_total=True,
            total_type="overall_after"  # overall total after caps
        )
        level1_qs = HQLAStock.objects.filter(
            fic_mis_date=fic_mis_date, 
            is_total=True,
            total_type="level1"
        )
        level2a_after_qs = HQLAStock.objects.filter(
            fic_mis_date=fic_mis_date, 
            is_total=True,
            total_type="level2a_after"
        )
        level2b_after_qs = HQLAStock.objects.filter(
            fic_mis_date=fic_mis_date, 
            is_total=True,
            total_type="level2b_after"
        )

        # Group totals by currency
        overall_hqla = {}
        for rec in overall_hqla_qs:
            overall_hqla[rec.v_ccy_code] = rec

        level1 = {}
        for rec in level1_qs:
            level1[rec.v_ccy_code] = rec

        level2a_after = {}
        for rec in level2a_after_qs:
            level2a_after[rec.v_ccy_code] = rec

            level1

        level2b_after = {}
        for rec in level2b_after_qs:
            level2b_after[rec.v_ccy_code] = rec

        print(f"🔹 HQLA Totals - Overall (After Caps): {len(overall_hqla)} record(s), "
              f"Level 1 : {len(level1)} record(s), "
              f"Level 2A After: {len(level2a_after)} record(s), "
              f"Level 2B After: {len(level2b_after)} record(s).")

        # =============================
        # Process HQLAStockInflow totals
        # =============================
        overall_inflows_qs = HQLAStockInflow.objects.filter(
            fic_mis_date=fic_mis_date,
            is_total=True,
            total_type="overall"
        )
        level_inflows_qs = HQLAStockInflow.objects.filter(
            fic_mis_date=fic_mis_date,
            is_total=True,
            total_type="level"
        )

        overall_inflows = {}
        for rec in overall_inflows_qs:
            overall_inflows[rec.v_ccy_code] = rec

        # Build dictionary: currency -> { hqla_level: record, ... }
        inflow_levels_by_ccy = {}
        for rec in level_inflows_qs:
            ccy = rec.v_ccy_code
            if ccy not in inflow_levels_by_ccy:
                inflow_levels_by_ccy[ccy] = {}
            inflow_levels_by_ccy[ccy][rec.hqla_level] = rec

        print(f"🔹 Inflow Totals - Overall: {len(overall_inflows)} record(s), "
              f"Distinct Levels: {sum(len(levels) for levels in inflow_levels_by_ccy.values())} record(s).")

        # =============================
        # Process HQLAStockOutflow totals
        # =============================
        overall_outflows_qs = HQLAStockOutflow.objects.filter(
            fic_mis_date=fic_mis_date,
            is_total=True,
            total_type="overall"
        )
        level_outflows_qs = HQLAStockOutflow.objects.filter(
            fic_mis_date=fic_mis_date,
            is_total=True,
            total_type="level"
        )

        overall_outflows = {}
        for rec in overall_outflows_qs:
            overall_outflows[rec.v_ccy_code] = rec

        outflow_levels_by_ccy = {}
        for rec in level_outflows_qs:
            ccy = rec.v_ccy_code
            if ccy not in outflow_levels_by_ccy:
                outflow_levels_by_ccy[ccy] = {}
            outflow_levels_by_ccy[ccy][rec.hqla_level] = rec

        print(f"🔹 Outflow Totals - Overall: {len(overall_outflows)} record(s), "
              f"Distinct Levels: {sum(len(levels) for levels in outflow_levels_by_ccy.values())} record(s).")

        # =============================
        # Build LCRCalculation records
        # =============================
        insertable_rows = []
        # Determine all currencies from any category
        currencies = set(list(overall_hqla.keys()) + list(overall_inflows.keys()) + list(overall_outflows.keys()))
        
        with transaction.atomic():
            for ccy in currencies:
                # --- Process HQLA totals ---
                # First add level totals, then the overall HQLA total.
                level1_rec = level1.get(ccy)
                level2a_rec = level2a_after.get(ccy)
                level2b_rec = level2b_after.get(ccy)
                hqla_rec = overall_hqla.get(ccy)

                if level1_rec:
                    insertable_rows.append(LCRCalculation(
                        fic_mis_date=fic_mis_date,
                        category="HIGH-QUALITY LIQUID ASSETS",
                        v_prod_type="Total Level 1 HQLA (USD)",
                        v_product_name="Total Level 1 HQLA",
                        hqla_level="Level 1",
                        n_amount=level2a_rec.n_amount,
                        v_ccy_code=ccy,
                        weighted_amount=level2a_rec.weighted_amount,
                        adjusted_amount=level2a_rec.adjusted_amount,
                        total_type="level"
                    ))
                if level2a_rec:
                    insertable_rows.append(LCRCalculation(
                        fic_mis_date=fic_mis_date,
                        category="HIGH-QUALITY LIQUID ASSETS",
                        v_prod_type="Total Level 2A HQLA (After Cap)",
                        v_product_name="Total Level 2A High-Quality Liquid Assets (After Cap)",
                        hqla_level="Level 2A",
                        n_amount=level2a_rec.n_amount,
                        v_ccy_code=ccy,
                        weighted_amount=level2a_rec.weighted_amount,
                        adjusted_amount=level2a_rec.adjusted_amount,
                        total_type="level"
                    ))
                if level2b_rec:
                    insertable_rows.append(LCRCalculation(
                        fic_mis_date=fic_mis_date,
                        category="HIGH-QUALITY LIQUID ASSETS",
                        v_prod_type="Total Level 2B HQLA (After Cap)",
                        v_product_name="Total Level 2B High-Quality Liquid Assets (After Cap)",
                        hqla_level="Level 2B",
                        n_amount=level2b_rec.n_amount,
                        v_ccy_code=ccy,
                        weighted_amount=level2b_rec.weighted_amount,
                        adjusted_amount=level2b_rec.adjusted_amount,
                        total_type="level"
                    ))
                if hqla_rec:
                    insertable_rows.append(LCRCalculation(
                        fic_mis_date=fic_mis_date,
                        category="HIGH-QUALITY LIQUID ASSETS",
                        v_prod_type="Total HQLA (Overall After Caps)",
                        v_product_name="Total High-Quality Liquid Assets (Overall After Caps)",
                        hqla_level="HQLA",
                        n_amount=hqla_rec.n_amount,
                        v_ccy_code=ccy,
                        weighted_amount=hqla_rec.weighted_amount,
                        adjusted_amount=hqla_rec.adjusted_amount,
                        total_type="overall_after"
                    ))
                    
                # --- Process Inflow totals ---
                # First, add level totals then the overall inflow total.
                inflow_level_recs = inflow_levels_by_ccy.get(ccy, {})
                for level, rec in inflow_level_recs.items():
                    insertable_rows.append(LCRCalculation(
                        fic_mis_date=fic_mis_date,
                        category="CASH INFLOWS",
                        v_prod_type=rec.v_prod_type,
                        v_product_name=rec.v_product_name,
                        hqla_level=rec.hqla_level,
                        n_amount=rec.n_amount,
                        v_ccy_code=ccy,
                        weighted_amount=rec.weighted_amount,
                        adjusted_amount=rec.adjusted_amount,
                        total_type="level"
                    ))
                inflow_overall_rec = overall_inflows.get(ccy)
                if inflow_overall_rec:
                    insertable_rows.append(LCRCalculation(
                        fic_mis_date=fic_mis_date,
                        category="CASH INFLOWS",
                        v_prod_type="Total Cash Inflows (Overall)",
                        v_product_name="Total Cash Inflows for LCR (Overall)",
                        hqla_level="LCR Inflows",
                        n_amount=inflow_overall_rec.n_amount,
                        v_ccy_code=ccy,
                        weighted_amount=inflow_overall_rec.weighted_amount,
                        adjusted_amount=inflow_overall_rec.adjusted_amount,
                        total_type="overall"
                    ))
                    
                # --- Process Outflow totals ---
                # First, add level totals then the overall outflow total.
                outflow_level_recs = outflow_levels_by_ccy.get(ccy, {})
                for level, rec in outflow_level_recs.items():
                    insertable_rows.append(LCRCalculation(
                        fic_mis_date=fic_mis_date,
                        category="CASH OUTFLOWS",
                        v_prod_type=rec.v_prod_type,
                        v_product_name=rec.v_product_name,
                        hqla_level=rec.hqla_level,
                        n_amount=rec.n_amount,
                        v_ccy_code=ccy,
                        weighted_amount=rec.weighted_amount,
                        adjusted_amount=rec.adjusted_amount,
                        total_type="level"
                    ))
                outflow_overall_rec = overall_outflows.get(ccy)
                if outflow_overall_rec:
                    insertable_rows.append(LCRCalculation(
                        fic_mis_date=fic_mis_date,
                        category="CASH OUTFLOWS",
                        v_prod_type="Total Cash Outflows (Overall)",
                        v_product_name="Total Cash Outflows for LCR (Overall)",
                        hqla_level="LCR Outflows",
                        n_amount=outflow_overall_rec.n_amount,
                        v_ccy_code=ccy,
                        weighted_amount=outflow_overall_rec.weighted_amount,
                        adjusted_amount=outflow_overall_rec.adjusted_amount,
                        total_type="overall"
                    ))
                    
                # --- Calculate Net Cash Outflows & LCR Ratio ---
                # Proceed only if overall inflow, overall outflow, and overall HQLA totals are available.
                if inflow_overall_rec and outflow_overall_rec and hqla_rec:
                    total_inflows = inflow_overall_rec.adjusted_amount
                    total_outflows = outflow_overall_rec.adjusted_amount
                    # Apply a 75% cap on inflows relative to outflows.
                    capped_inflows = min(total_inflows, Decimal("0.75") * total_outflows)
                    net_cash_outflows = total_outflows - capped_inflows
                    total_hqla = hqla_rec.adjusted_amount
                    lcr_ratio = (total_hqla / net_cash_outflows * Decimal(100)) if net_cash_outflows > 0 else Decimal(0)

                    # Insert a record for Net Cash Outflows
                    insertable_rows.append(LCRCalculation(
                        fic_mis_date=fic_mis_date,
                        category="NET CASH OUTFLOWS",
                        v_prod_type="Net Cash Outflows",
                        v_product_name="Net Cash Outflows for LCR",
                        hqla_level="LCR Summary",
                        v_ccy_code=ccy,
                        net_cash_outflows=net_cash_outflows
                    ))
                    # Insert a record for LCR Ratio
                    insertable_rows.append(LCRCalculation(
                        fic_mis_date=fic_mis_date,
                        category="LCR RATIO",
                        v_prod_type="LCR Ratio",
                        v_product_name="Liquidity Coverage Ratio (%)",
                        hqla_level="LCR Summary",
                        v_ccy_code=ccy,
                        lcr_ratio=lcr_ratio
                    ))

            # Bulk insert all LCRCalculation records
            LCRCalculation.objects.bulk_create(insertable_rows)

        print(f"✅ Successfully stored {len(insertable_rows)} LCR record(s) based on HQLA, Inflow, and Outflow totals.")

    except Exception as e:
        print(f"❌ Error in calculate_and_store_lcr: {e}")
