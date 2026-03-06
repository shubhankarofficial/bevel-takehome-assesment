-- NOTIFY on foods/food_nutrients changes for dynamic search index sync (Phase 1).
-- Channel: food_index_events. Payload: {"table":"foods"|"food_nutrients","op":"INSERT"|"UPDATE"|"DELETE","fdc_id":<int>}
-- Listener (separate process) will LISTEN and upsert/delete the corresponding ES document.

-- Trigger function for foods: notify only when foundation_food is involved.
CREATE OR REPLACE FUNCTION notify_food_index_on_foods()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  payload json;
  should_notify boolean := false;
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.data_type = 'foundation_food' THEN
      should_notify := true;
      payload := json_build_object('table', 'foods', 'op', 'DELETE', 'fdc_id', OLD.fdc_id);
    END IF;
  ELSIF TG_OP = 'INSERT' THEN
    IF NEW.data_type = 'foundation_food' THEN
      should_notify := true;
      payload := json_build_object('table', 'foods', 'op', 'INSERT', 'fdc_id', NEW.fdc_id);
    END IF;
  ELSIF TG_OP = 'UPDATE' THEN
    IF OLD.data_type = 'foundation_food' OR NEW.data_type = 'foundation_food' THEN
      should_notify := true;
      payload := json_build_object('table', 'foods', 'op', 'UPDATE', 'fdc_id', COALESCE(NEW.fdc_id, OLD.fdc_id));
    END IF;
  END IF;

  IF should_notify THEN
    PERFORM pg_notify('food_index_events', payload::text);
  END IF;

  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  ELSE
    RETURN NEW;
  END IF;
END;
$$;

-- Trigger function for food_nutrients: always notify with fdc_id so listener can refresh that food's doc.
CREATE OR REPLACE FUNCTION notify_food_index_on_food_nutrients()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  payload json;
  fdc bigint;
BEGIN
  IF TG_OP = 'DELETE' THEN
    fdc := OLD.fdc_id;
  ELSE
    fdc := NEW.fdc_id;
  END IF;
  payload := json_build_object('table', 'food_nutrients', 'op', TG_OP, 'fdc_id', fdc);
  PERFORM pg_notify('food_index_events', payload::text);

  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  ELSE
    RETURN NEW;
  END IF;
END;
$$;

-- Attach triggers (idempotent: drop if exists then create).
DROP TRIGGER IF EXISTS tr_food_index_notify ON foods;
CREATE TRIGGER tr_food_index_notify
  AFTER INSERT OR UPDATE OR DELETE ON foods
  FOR EACH ROW
  EXECUTE FUNCTION notify_food_index_on_foods();

DROP TRIGGER IF EXISTS tr_food_index_notify ON food_nutrients;
CREATE TRIGGER tr_food_index_notify
  AFTER INSERT OR UPDATE OR DELETE ON food_nutrients
  FOR EACH ROW
  EXECUTE FUNCTION notify_food_index_on_food_nutrients();
