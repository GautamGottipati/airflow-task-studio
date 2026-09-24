import { useEffect, useMemo, useState } from "react";

type TaskStudioPluginContext = {
  dagId?: string;
  taskId?: string;
  runId?: string;
  mapIndex?: number;
};

type AppProps = {
  pluginContext?: TaskStudioPluginContext;
};

type EditableTask = {
  dag_id: string;
  task_id: string;
  file: string;
};

type TaskParameter = {
  name: string;
  type: string | null;
  default: unknown;
  has_default: boolean;

  config?: {
    choices?: unknown[];
    min?: number;
    max?: number;
    description?: string;
    editable?: boolean;
  };
};

type TaskDetails = {
  dag_id: string;
  task_id: string;
  file: string;
  editable: boolean;
  parameters: TaskParameter[];
  code: string;
};

type PendingOverride = {
  dag_id: string;
  task_id: string;
  scope: string;
  values: Record<string, unknown>;
};

/*
 * NEW
 *
 * Represents one historical Task Studio
 * override event.
 */
type OverrideHistoryEntry = {
  override_id: string;
  dag_id: string;
  task_id: string;
  scope: string;

  values: Record<string, unknown>;

  status:
    | "pending"
    | "cancelled"
    | "claimed"
    | "consumed"
    | string;

  created_at: string;

  run_id: string | null;
  try_number: number | null;
  map_index: number | null;

  consumed_at: string | null;
  cancelled_at: string | null;
};

type EditedValues = Record<string, string>;

function App({ pluginContext }: AppProps) {
  const contextualDagId = pluginContext?.dagId;
  const contextualTaskId = pluginContext?.taskId;

  const isContextMode =
    Boolean(contextualDagId) &&
    Boolean(contextualTaskId);

  const [tasks, setTasks] =
    useState<EditableTask[]>([]);

  const [selectedTask, setSelectedTask] =
    useState<EditableTask | null>(null);

  const [taskDetails, setTaskDetails] =
    useState<TaskDetails | null>(null);

  const [editedValues, setEditedValues] =
    useState<EditedValues>({});

  const [pendingOverride, setPendingOverride] =
    useState<PendingOverride | null>(null);

  /*
   * NEW
   *
   * Override history state.
   */
  const [overrideHistory, setOverrideHistory] =
    useState<OverrideHistoryEntry[]>([]);

  const [loadingHistory, setLoadingHistory] =
    useState(false);

  const [showHistory, setShowHistory] =
    useState(false);

  const [loadingTasks, setLoadingTasks] =
    useState(!isContextMode);

  const [loadingDetails, setLoadingDetails] =
    useState(false);

  const [loadingOverride, setLoadingOverride] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const [showPreview, setShowPreview] =
    useState(false);

  const [applying, setApplying] =
    useState(false);

  const [
    cancellingOverride,
    setCancellingOverride,
  ] = useState(false);

  const [applyMessage, setApplyMessage] =
    useState<string | null>(null);

  /*
   * GLOBAL MODE
   */
  useEffect(() => {
    if (isContextMode) {
      return;
    }

    setLoadingTasks(true);

    fetch("/task-studio/api/tasks")
      .then((response) => {
        if (!response.ok) {
          throw new Error(
            `Failed to load tasks: ${response.status}`
          );
        }

        return response.json();
      })
      .then((data) => {
        setTasks(data.tasks);

        if (data.tasks.length > 0) {
          setSelectedTask(data.tasks[0]);
        }
      })
      .catch((err: Error) => {
        setError(err.message);
      })
      .finally(() => {
        setLoadingTasks(false);
      });
  }, [isContextMode]);

  /*
   * CONTEXT MODE
   */
  useEffect(() => {
    if (
      !isContextMode ||
      !contextualDagId ||
      !contextualTaskId
    ) {
      return;
    }

    setSelectedTask({
      dag_id: contextualDagId,
      task_id: contextualTaskId,
      file: "",
    });
  }, [
    isContextMode,
    contextualDagId,
    contextualTaskId,
  ]);

  /*
   * LOAD PENDING OVERRIDE
   */
  const loadPendingOverride = async (
    dagId: string,
    taskId: string
  ) => {
    setLoadingOverride(true);

    try {
      const response = await fetch(
        `/task-studio/api/overrides/${dagId}/${taskId}`
      );

      if (!response.ok) {
        throw new Error(
          `Failed to load pending override: ${response.status}`
        );
      }

      const data = await response.json();

      setPendingOverride(
        data.override ?? null
      );
    } catch (err) {
      console.error(
        "Failed to load pending override",
        err
      );

      setPendingOverride(null);
    } finally {
      setLoadingOverride(false);
    }
  };

  /*
   * NEW
   *
   * LOAD OVERRIDE HISTORY
   */
  const loadOverrideHistory = async (
    dagId: string,
    taskId: string
  ) => {
    setLoadingHistory(true);

    try {
      const response = await fetch(
        `/task-studio/api/history/${dagId}/${taskId}`
      );

      if (!response.ok) {
        throw new Error(
          `Failed to load override history: ${response.status}`
        );
      }

      const data = await response.json();

      setOverrideHistory(
        data.history ?? []
      );
    } catch (err) {
      console.error(
        "Failed to load override history",
        err
      );

      setOverrideHistory([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  /*
   * NEW
   *
   * Format UTC backend timestamps using
   * the browser's local timezone.
   */
  const formatTimestamp = (
    value: string | null
  ) => {
    if (!value) {
      return "—";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return date.toLocaleString();
  };

  /*
   * LOAD TASK DETAILS
   */
  useEffect(() => {
    if (!selectedTask) {
      return;
    }

    setLoadingDetails(true);
    setShowPreview(false);
    setApplyMessage(null);
    setError(null);

    /*
     * Reset state when moving between tasks.
     */
    setPendingOverride(null);
    setOverrideHistory([]);
    setShowHistory(false);

    fetch(
      `/task-studio/api/task/${selectedTask.dag_id}/${selectedTask.task_id}`
    )
      .then((response) => {
        if (!response.ok) {
          throw new Error(
            `Failed to load task details: ${response.status}`
          );
        }

        return response.json();
      })
      .then((data: TaskDetails) => {
        setTaskDetails(data);

        const initialValues: EditedValues = {};

        data.parameters.forEach((parameter) => {
          initialValues[parameter.name] =
            parameter.has_default
              ? String(
                  parameter.default ?? ""
                )
              : "";
        });

        setEditedValues(initialValues);

        /*
         * Load both runtime state and
         * historical state.
         */
        void loadPendingOverride(
          data.dag_id,
          data.task_id
        );

        void loadOverrideHistory(
          data.dag_id,
          data.task_id
        );
      })
      .catch((err: Error) => {
        setTaskDetails(null);
        setPendingOverride(null);
        setOverrideHistory([]);
        setError(err.message);
      })
      .finally(() => {
        setLoadingDetails(false);
      });
  }, [selectedTask]);

  /*
   * DETECT CHANGES
   */
  const changes = useMemo(() => {
    if (!taskDetails) {
      return [];
    }

    return taskDetails.parameters
      .map((parameter) => {
        const originalValue =
          parameter.has_default
            ? String(
                parameter.default ?? ""
              )
            : "";

        const editedValue =
          editedValues[
            parameter.name
          ] ?? "";

        return {
          name: parameter.name,
          type: parameter.type,
          originalValue,
          editedValue,
          changed:
            originalValue !==
            editedValue,
        };
      })
      .filter(
        (change) => change.changed
      );
  }, [taskDetails, editedValues]);

  /*
   * COMMON PARAMETER CHANGE HANDLER
   */
  const updateParameter = (
    name: string,
    value: string
  ) => {
    setEditedValues((current) => ({
      ...current,
      [name]: value,
    }));

    setShowPreview(false);
    setApplyMessage(null);
  };

  /*
   * APPLY OVERRIDE
   */
  const applyOverride = async () => {
    if (
      !taskDetails ||
      changes.length === 0
    ) {
      return;
    }

    setApplying(true);
    setApplyMessage(null);
    setError(null);

    const values: Record<
      string,
      string
    > = {};

    changes.forEach((change) => {
      values[change.name] =
        change.editedValue;
    });

    try {
      const response = await fetch(
        "/task-studio/api/overrides",
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            dag_id:
              taskDetails.dag_id,

            task_id:
              taskDetails.task_id,

            values,
          }),
        }
      );

      if (!response.ok) {
        let message =
          `Failed to apply override: ${response.status}`;

        try {
          const errorBody =
            await response.json();

          if (errorBody.detail) {
            message =
              errorBody.detail;
          }
        } catch {
          // Keep fallback HTTP error.
        }

        throw new Error(message);
      }

      await response.json();

      /*
       * Refresh pending override immediately.
       */
      await loadPendingOverride(
        taskDetails.dag_id,
        taskDetails.task_id
      );

      /*
       * NEW
       *
       * Refresh history immediately so the
       * new PENDING entry appears.
       */
      await loadOverrideHistory(
        taskDetails.dag_id,
        taskDetails.task_id
      );

      setApplyMessage(
        "Override saved. It will be applied to the next run."
      );

      setShowPreview(false);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError(
          "Failed to apply override."
        );
      }
    } finally {
      setApplying(false);
    }
  };

  /*
   * CANCEL PENDING OVERRIDE
   */
  const cancelPendingOverride =
    async () => {
      if (!taskDetails) {
        return;
      }

      setCancellingOverride(true);
      setApplyMessage(null);
      setError(null);

      try {
        const response = await fetch(
          `/task-studio/api/overrides/${taskDetails.dag_id}/${taskDetails.task_id}`,
          {
            method: "DELETE",
          }
        );

        if (!response.ok) {
          let message =
            `Failed to cancel override: ${response.status}`;

          try {
            const errorBody =
              await response.json();

            if (errorBody.detail) {
              message =
                errorBody.detail;
            }
          } catch {
            // Keep fallback HTTP error.
          }

          throw new Error(message);
        }

        await response.json();

        setPendingOverride(null);

        /*
         * NEW
         *
         * The backend changed the history
         * entry from PENDING -> CANCELLED.
         */
        await loadOverrideHistory(
          taskDetails.dag_id,
          taskDetails.task_id
        );

        setApplyMessage(
          "Pending override cancelled."
        );
      } catch (err) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError(
            "Failed to cancel pending override."
          );
        }
      } finally {
        setCancellingOverride(false);
      }
    };

  if (loadingTasks) {
    return (
      <div
        style={{
          padding: "32px",
        }}
      >
        Loading Task Studio...
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        minHeight: "600px",
      }}
    >
      {/* GLOBAL MODE SIDEBAR */}
      {!isContextMode && (
        <div
          style={{
            width: "260px",
            borderRight:
              "1px solid #444",
            padding: "24px",
          }}
        >
          <h2>Editable Tasks</h2>

          {tasks.length === 0 && (
            <p>
              No editable tasks found.
            </p>
          )}

          {tasks.map((task) => {
            const selected =
              selectedTask?.dag_id ===
                task.dag_id &&
              selectedTask?.task_id ===
                task.task_id;

            return (
              <button
                key={
                  `${task.dag_id}-${task.task_id}`
                }
                onClick={() => {
                  setSelectedTask(task);
                }}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  marginBottom: "10px",
                  padding: "10px",

                  fontWeight:
                    selected
                      ? "bold"
                      : "normal",
                }}
              >
                <div>
                  {task.task_id}
                </div>

                <small>
                  {task.dag_id}
                </small>
              </button>
            );
          })}
        </div>
      )}

      {/* MAIN CONTENT */}
      <div
        style={{
          flex: 1,
          padding: "32px",
          maxWidth: "900px",
        }}
      >
        <h1>Task Studio</h1>

        {isContextMode ? (
          <p>
            Tune this task safely
            without editing the DAG
            source.
          </p>
        ) : (
          <p>
            Inspect and safely tune
            your Airflow tasks.
          </p>
        )}

        {/* CONTEXTUAL RUN INFORMATION */}
        {isContextMode &&
          pluginContext?.runId && (
            <div
              style={{
                marginTop: "12px",
                marginBottom: "20px",
                opacity: 0.75,
              }}
            >
              Current run:{" "}
              <code>
                {
                  pluginContext.runId
                }
              </code>
            </div>
          )}

        {/* ERROR */}
        {error && (
          <div
            style={{
              marginTop: "16px",
              padding: "12px",
              border:
                "1px solid #555",
              borderRadius: "6px",
            }}
          >
            Error: {error}
          </div>
        )}

        {/* LOADING */}
        {loadingDetails && (
          <p>
            Loading task details...
          </p>
        )}

        {/* TASK */}
        {taskDetails &&
          !loadingDetails && (
            <>
              <hr />

              <p>
                <strong>
                  DAG:
                </strong>{" "}
                {taskDetails.dag_id}
              </p>

              <p>
                <strong>
                  Task:
                </strong>{" "}
                {taskDetails.task_id}
              </p>

              {!isContextMode && (
                <p>
                  <strong>
                    File:
                  </strong>{" "}
                  {taskDetails.file}
                </p>
              )}

              {/* PENDING OVERRIDE */}
              {loadingOverride && (
                <p>
                  Checking for pending
                  override...
                </p>
              )}

              {!loadingOverride &&
                pendingOverride && (
                  <div
                    style={{
                      marginTop: "24px",
                      marginBottom:
                        "28px",
                      padding: "18px",
                      border:
                        "1px solid #777",
                      borderRadius:
                        "8px",
                    }}
                  >
                    <div
                      style={{
                        fontWeight: 700,
                        fontSize: "16px",
                        marginBottom:
                          "6px",
                      }}
                    >
                      ⚠ Pending override
                      for next run
                    </div>

                    <div
                      style={{
                        fontSize: "13px",
                        opacity: 0.7,
                        marginBottom:
                          "16px",
                      }}
                    >
                      The next execution
                      of this task will
                      use these temporary
                      values.
                    </div>

                    {Object.entries(
                      pendingOverride.values
                    ).map(
                      ([
                        name,
                        value,
                      ]) => {
                        const parameter =
                          taskDetails.parameters.find(
                            (
                              item
                            ) =>
                              item.name ===
                              name
                          );

                        const defaultValue =
                          parameter?.has_default
                            ? String(
                                parameter.default ??
                                  ""
                              )
                            : "—";

                        return (
                          <div
                            key={name}
                            style={{
                              marginBottom:
                                "12px",
                            }}
                          >
                            <strong>
                              {name}
                            </strong>

                            <div
                              style={{
                                marginTop:
                                  "4px",
                              }}
                            >
                              <code>
                                {
                                  defaultValue
                                }
                              </code>

                              {" → "}

                              <code>
                                {String(
                                  value
                                )}
                              </code>
                            </div>
                          </div>
                        );
                      }
                    )}

                    <button
                      onClick={
                        cancelPendingOverride
                      }
                      disabled={
                        cancellingOverride
                      }
                      style={{
                        marginTop: "8px",
                      }}
                    >
                      {cancellingOverride
                        ? "Cancelling..."
                        : "Cancel Override"}
                    </button>
                  </div>
                )}

              {/* OVERRIDE HISTORY */}
              <div
                style={{
                  marginTop: "24px",
                  marginBottom: "28px",
                  border:
                    "1px solid #555",
                  borderRadius: "8px",
                  overflow: "hidden",
                }}
              >
                <button
                  type="button"
                  onClick={() =>
                    setShowHistory(
                      (current) =>
                        !current
                    )
                  }
                  style={{
                    width: "100%",
                    padding:
                      "14px 16px",
                    textAlign: "left",
                    fontWeight: 700,
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  Override History (
                  {overrideHistory.length})
                  {" "}
                  {showHistory
                    ? "▴"
                    : "▾"}
                </button>

                {showHistory && (
                  <div
                    style={{
                      padding: "16px",
                      borderTop:
                        "1px solid #555",
                    }}
                  >
                    {loadingHistory ? (
                      <p>
                        Loading
                        history...
                      </p>
                    ) : overrideHistory.length ===
                      0 ? (
                      <p
                        style={{
                          opacity: 0.7,
                        }}
                      >
                        No Task Studio
                        overrides have
                        been created for
                        this task yet.
                      </p>
                    ) : (
                      overrideHistory.map(
                        (entry) => {
                          const status =
                            entry.status.toUpperCase();

                          return (
                            <div
                              key={
                                entry.override_id
                              }
                              style={{
                                marginBottom:
                                  "20px",
                                paddingBottom:
                                  "20px",
                                borderBottom:
                                  "1px solid #444",
                              }}
                            >
                              {/* HISTORY HEADER */}
                              <div
                                style={{
                                  display:
                                    "flex",
                                  justifyContent:
                                    "space-between",
                                  alignItems:
                                    "flex-start",
                                  gap: "16px",
                                  marginBottom:
                                    "12px",
                                }}
                              >
                                <strong>
                                  {status ===
                                  "PENDING"
                                    ? "● "
                                    : status ===
                                        "CONSUMED"
                                      ? "✓ "
                                      : status ===
                                          "CANCELLED"
                                        ? "⊘ "
                                        : status ===
                                            "CLAIMED"
                                          ? "◐ "
                                          : ""}

                                  {status}
                                </strong>

                                <span
                                  style={{
                                    fontSize:
                                      "12px",
                                    opacity:
                                      0.7,
                                    textAlign:
                                      "right",
                                  }}
                                >
                                  {formatTimestamp(
                                    entry.created_at
                                  )}
                                </span>
                              </div>

                              {/* CHANGED VALUES */}
                              {Object.entries(
                                entry.values
                              ).map(
                                ([
                                  name,
                                  value,
                                ]) => {
                                  const parameter =
                                    taskDetails.parameters.find(
                                      (
                                        item
                                      ) =>
                                        item.name ===
                                        name
                                    );

                                  const defaultValue =
                                    parameter?.has_default
                                      ? String(
                                          parameter.default ??
                                            ""
                                        )
                                      : "—";

                                  return (
                                    <div
                                      key={
                                        name
                                      }
                                      style={{
                                        marginBottom:
                                          "10px",
                                      }}
                                    >
                                      <strong>
                                        {
                                          name
                                        }
                                      </strong>

                                      <div
                                        style={{
                                          marginTop:
                                            "3px",
                                        }}
                                      >
                                        <code>
                                          {
                                            defaultValue
                                          }
                                        </code>

                                        {
                                          " → "
                                        }

                                        <code>
                                          {String(
                                            value
                                          )}
                                        </code>
                                      </div>
                                    </div>
                                  );
                                }
                              )}

                              {/* EXECUTION INFO */}
                              {entry.run_id && (
                                <div
                                  style={{
                                    marginTop:
                                      "12px",
                                    fontSize:
                                      "12px",
                                    opacity:
                                      0.75,
                                  }}
                                >
                                  Run:{" "}
                                  <code>
                                    {
                                      entry.run_id
                                    }
                                  </code>
                                </div>
                              )}

                              {entry.try_number !==
                                null && (
                                <div
                                  style={{
                                    marginTop:
                                      "4px",
                                    fontSize:
                                      "12px",
                                    opacity:
                                      0.75,
                                  }}
                                >
                                  Try:{" "}
                                  {
                                    entry.try_number
                                  }
                                </div>
                              )}

                              {entry.map_index !==
                                null && (
                                <div
                                  style={{
                                    marginTop:
                                      "4px",
                                    fontSize:
                                      "12px",
                                    opacity:
                                      0.75,
                                  }}
                                >
                                  Map index:{" "}
                                  {
                                    entry.map_index
                                  }
                                </div>
                              )}

                              {/* CANCELLED TIME */}
                              {entry.cancelled_at && (
                                <div
                                  style={{
                                    marginTop:
                                      "12px",
                                    fontSize:
                                      "12px",
                                    opacity:
                                      0.7,
                                  }}
                                >
                                  Cancelled:{" "}
                                  {formatTimestamp(
                                    entry.cancelled_at
                                  )}
                                </div>
                              )}

                              {/* CONSUMED TIME */}
                              {entry.consumed_at && (
                                <div
                                  style={{
                                    marginTop:
                                      "12px",
                                    fontSize:
                                      "12px",
                                    opacity:
                                      0.7,
                                  }}
                                >
                                  Consumed:{" "}
                                  {formatTimestamp(
                                    entry.consumed_at
                                  )}
                                </div>
                              )}

                              {/* OVERRIDE ID */}
                              <div
                                style={{
                                  marginTop:
                                    "12px",
                                  fontSize:
                                    "11px",
                                  opacity:
                                    0.5,
                                  overflowWrap:
                                    "anywhere",
                                }}
                              >
                                Override{" "}
                                <code>
                                  {
                                    entry.override_id
                                  }
                                </code>
                              </div>
                            </div>
                          );
                        }
                      )
                    )}
                  </div>
                )}
              </div>

              <h2>Parameters</h2>

              {taskDetails.parameters
                .length === 0 && (
                <p>
                  This task has no
                  editable parameters.
                </p>
              )}

              {taskDetails.parameters.map(
                (parameter) => {
                  const config =
                    parameter.config ??
                    {};

                  const value =
                    editedValues[
                      parameter.name
                    ] ?? "";

                  const hasChoices =
                    Array.isArray(
                      config.choices
                    ) &&
                    config.choices
                      .length > 0;

                  const isNumeric =
                    parameter.type ===
                      "int" ||
                    parameter.type ===
                      "float";

                  return (
                    <div
                      key={
                        parameter.name
                      }
                      style={{
                        marginBottom:
                          "24px",
                      }}
                    >
                      {/* PARAMETER NAME */}
                      <div
                        style={{
                          marginBottom:
                            "4px",
                        }}
                      >
                        <strong>
                          {
                            parameter.name
                          }
                        </strong>

                        {parameter.type && (
                          <span
                            style={{
                              marginLeft:
                                "8px",
                              opacity:
                                0.7,
                            }}
                          >
                            (
                            {
                              parameter.type
                            }
                            )
                          </span>
                        )}
                      </div>

                      {/* DESCRIPTION */}
                      {config.description && (
                        <div
                          style={{
                            fontSize:
                              "13px",
                            opacity: 0.7,
                            marginBottom:
                              "8px",
                          }}
                        >
                          {
                            config.description
                          }
                        </div>
                      )}

                      {/* CHOICES */}
                      {hasChoices ? (
                        <select
                          value={value}
                          onChange={(
                            event
                          ) =>
                            updateParameter(
                              parameter.name,
                              event.target
                                .value
                            )
                          }
                          style={{
                            padding:
                              "8px",
                            width:
                              "350px",
                          }}
                        >
                          {config.choices!.map(
                            (choice) => (
                              <option
                                key={String(
                                  choice
                                )}
                                value={String(
                                  choice
                                )}
                              >
                                {String(
                                  choice
                                )}
                              </option>
                            )
                          )}
                        </select>
                      ) : (
                        <input
                          type={
                            isNumeric
                              ? "number"
                              : "text"
                          }
                          value={value}
                          min={
                            config.min
                          }
                          max={
                            config.max
                          }
                          step={
                            parameter.type ===
                            "float"
                              ? "any"
                              : undefined
                          }
                          onChange={(
                            event
                          ) =>
                            updateParameter(
                              parameter.name,
                              event.target
                                .value
                            )
                          }
                          style={{
                            padding:
                              "8px",
                            width:
                              "350px",
                          }}
                        />
                      )}

                      {/* MIN/MAX */}
                      {(config.min !==
                        undefined ||
                        config.max !==
                          undefined) && (
                        <div
                          style={{
                            fontSize:
                              "12px",
                            opacity: 0.7,
                            marginTop:
                              "6px",
                          }}
                        >
                          Allowed:{" "}
                          {config.min ??
                            "no minimum"}{" "}
                          to{" "}
                          {config.max ??
                            "no maximum"}
                        </div>
                      )}

                      {/* DEFAULT VALUE */}
                      {parameter.has_default && (
                        <div
                          style={{
                            fontSize:
                              "12px",
                            opacity: 0.6,
                            marginTop:
                              "4px",
                          }}
                        >
                          Default:{" "}
                          <code>
                            {String(
                              parameter.default
                            )}
                          </code>
                        </div>
                      )}
                    </div>
                  );
                }
              )}

              {/* ACTIONS */}
              <div
                style={{
                  marginTop: "24px",
                }}
              >
                <button
                  onClick={() => {
                    setShowPreview(
                      true
                    );
                  }}
                  disabled={
                    changes.length === 0
                  }
                  style={{
                    marginRight:
                      "12px",
                  }}
                >
                  Preview Changes
                </button>

                <button
                  onClick={
                    applyOverride
                  }
                  disabled={
                    changes.length ===
                      0 ||
                    applying
                  }
                >
                  {applying
                    ? "Applying..."
                    : "Apply for Next Run"}
                </button>
              </div>

              {/* SUCCESS */}
              {applyMessage && (
                <div
                  style={{
                    marginTop: "16px",
                    padding: "12px",
                    border:
                      "1px solid #555",
                    borderRadius:
                      "6px",
                  }}
                >
                  ✓ {applyMessage}
                </div>
              )}

              {/* CHANGE PREVIEW */}
              {showPreview && (
                <div
                  style={{
                    marginTop: "30px",
                    padding: "20px",
                    border:
                      "1px solid #555",
                    borderRadius:
                      "6px",
                  }}
                >
                  <h2>
                    Change Preview
                  </h2>

                  {changes.length ===
                  0 ? (
                    <p>
                      No changes
                      detected.
                    </p>
                  ) : (
                    changes.map(
                      (change) => (
                        <div
                          key={
                            change.name
                          }
                          style={{
                            marginBottom:
                              "20px",
                            paddingBottom:
                              "16px",
                            borderBottom:
                              "1px solid #444",
                          }}
                        >
                          <strong>
                            {
                              change.name
                            }
                          </strong>

                          <div
                            style={{
                              marginTop:
                                "8px",
                            }}
                          >
                            <div>
                              Current:{" "}
                              <code>
                                {
                                  change.originalValue
                                }
                              </code>
                            </div>

                            <div>
                              Proposed:{" "}
                              <code>
                                {
                                  change.editedValue
                                }
                              </code>
                            </div>
                          </div>
                        </div>
                      )
                    )
                  )}
                </div>
              )}

              {/* TASK CODE */}
              <h2
                style={{
                  marginTop: "32px",
                }}
              >
                Task Code
              </h2>

              <pre
                style={{
                  padding: "16px",
                  overflowX: "auto",
                  border:
                    "1px solid #555",
                  borderRadius: "6px",
                }}
              >
                {taskDetails.code}
              </pre>
            </>
          )}
      </div>
    </div>
  );
}

export default App;